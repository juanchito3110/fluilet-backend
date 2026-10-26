"""Bounded Spanish Wikipedia retrieval with contextual, attributed local fallback."""

import asyncio
import html
import json
import re
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from app.config import settings
from app.education import CATEGORIES, category_name, normalized
from app.encyclopedia import ARTICLES, BANK, Article
from app.nlp.segmentation import sentences, words

WIKIPEDIA_API = "https://es.wikipedia.org/w/api.php"
_CONTEXT = {
    "ciencia_espacio": "ciencia astronomía",
    "animales_naturaleza": "biología naturaleza",
    "historia_misterios": "historia civilización",
    "deportes": "deporte",
    "tecnologia": "tecnología informática",
    "cuentos_aventuras": "literatura novela",
}
_KEYWORDS = {
    "ciencia_espacio": "ciencia cientifico cientifica astronomia planeta planetas estrella estrellas solar tierra universo gravedad energia volcan atmosfera biologia oceano oceanos agua espacio",
    "animales_naturaleza": "biologia animal animales fauna flora oceano oceanos mar mares peces mamiferos agua seres ecosistema plantas naturaleza alimentacion",
    "historia_misterios": "historia civilizacion antiguo antigua siglo faraon arqueologia escritura imperio cultura reino egipto mapa cartografia",
    "deportes": "deporte deportivo deportiva futbol equipo equipos jugadores partido competicion estadio balon olimpicos juegos baloncesto atletismo",
    "tecnologia": "tecnologia robot robots maquina sensores programa informatica datos informacion algoritmo inteligencia ordenador software red internet electricidad",
    "cuentos_aventuras": "literatura novela escritor escritora libro cuentos cuento narracion autor personaje aventura ficcion publicado publicada",
}
_ALIASES = {
    "real madrid": "real madrid",
    "real madrid club de futbol": "real madrid",
    "futbol": "futbol",
    "balompie": "futbol",
    "baloncesto": "baloncesto",
    "olimpicos": "juegos olimpicos",
    "olimpico": "juegos olimpicos",
    "juegos olimpicos": "juegos olimpicos",
    "marina": "biologia marina",
    "marino": "biologia marina",
    "vida marina": "biologia marina",
    "fauna marina": "biologia marina",
    "biologia marina": "biologia marina",
    "biologia marina y fauna oceanica": "biologia marina",
    "tiburon": "tiburon",
    "tiburones": "tiburon",
    "dinosaurio": "dinosaurios",
    "dinosaurios": "dinosaurios",
    "sistema solar": "sistema solar",
    "solar": "sistema solar",
    "espacial": "sistema solar",
    "agujero negro": "agujeros negros",
    "agujeros negros": "agujeros negros",
    "volcan": "volcanes",
    "volcanes": "volcanes",
    "egipcia": "antiguo egipto",
    "egipcio": "antiguo egipto",
    "egipto": "antiguo egipto",
    "antiguo egipto": "antiguo egipto",
    "cultura egipcia": "antiguo egipto",
    "robot": "robots",
    "robots": "robots",
    "robotica": "robots",
    "robots e inteligencia artificial": "robots inteligencia artificial",
    "el viaje del pequeno faro": "pequeno faro",
    "inteligencia artificial": "inteligencia artificial",
    "artificial": "inteligencia artificial",
    "robots del oceano": "robots submarinos",
    "robots submarinos": "robots submarinos",
    "rov": "robots submarinos",
}
_STOP = set(
    "el la los las un una unos unas de del y e a en por para que con al es son su sus lo".split()
)


@dataclass(frozen=True)
class ResolvedTopic:
    category: str
    query: str
    title: str
    local_key: str | None


def resolve_topic(category, topic=None):
    category = category_name(category)
    if category not in CATEGORIES:
        category = CATEGORIES[0]
    if not topic:
        import secrets

        key = secrets.choice(BANK[category])
        entry = ARTICLES[key]
        return ResolvedTopic(category, entry.title, entry.title, key)
    key = normalized(" ".join(topic.split())).strip()
    key = _ALIASES.get(key, key if key in ARTICLES else None)
    # The same short adjective gets interpreted as marine science in both
    # relevant categories, never as a singer, military branch or given name.
    if key == "biologia marina" and category not in {"animales_naturaleza", "ciencia_espacio"}:
        key = None
    if key is not None:
        title = ARTICLES[key].title
        query = "Biología marina" if key == "biologia marina" else title
        return ResolvedTopic(category, query, title, key)
    for article_key, entry in ARTICLES.items():
        if normalized(topic) == normalized(entry.title):
            return ResolvedTopic(category, entry.title, entry.title, article_key)
    safe_topic = " ".join(words(topic))
    return ResolvedTopic(category, f"{safe_topic} {_CONTEXT[category]}", safe_topic, None)


def local_article(resolution):
    return ARTICLES.get(resolution.local_key)


def clean_extract(value):
    text = html.unescape(re.sub(r"<[^>]+>", "", value))
    text = re.sub(r"\[(?:\d+(?:[,–-]\d+)*|[a-z]|cita requerida)\]", "", text, flags=re.I)
    text = re.sub(
        r"\((?:(?:AFI|IPA|pronunciaci[oó]n)[^)]*|/[^)]*/|[^)]*[ˈˌ][^)]*)\)",
        "",
        text,
        flags=re.I,
    )
    lines = []
    for line in text.splitlines():
        if re.fullmatch(r"\s*(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2} de \w+ de \d{4})\s*", line):
            continue
        lines.append(line)
    text = " ".join(" ".join(lines).split())
    parts, count = [], 0
    for sentence in sentences(text):
        size = len(words(sentence))
        if count + size > 1200:
            break
        parts.append(sentence)
        count += size
    return " ".join(parts)


def _candidate_score(resolution, title, extract):
    if "desambiguacion" in normalized(title) or re.search(
        r"puede(?:n)? (?:referirse|hacer referencia) a", extract, re.I
    ):
        return None
    topic = set(words(normalized(resolution.title))) - _STOP
    title_words = set(words(normalized(title)))
    body_words = set(words(normalized(extract)))
    if not topic & (title_words | body_words):
        return None
    keywords = set(_KEYWORDS[resolution.category].split()) - topic
    context = len(keywords & body_words)
    # Known marine/science resolutions have an explicit context even if the UI
    # category is broad "science/space"; do not accept an unrelated exact name.
    if context == 0:
        return None
    exact = normalized(title) in {normalized(resolution.title), normalized(resolution.query)}
    return 40 * exact + 8 * len(topic & title_words) + 2 * len(topic & body_words) + context


class SourceUnavailable(ValueError):
    pass


class WikipediaSource:
    def __init__(self, transport=None):
        self.transport = transport
        self.slots = asyncio.Semaphore(4)

    async def _query(self, client, params):
        # POST keeps the user's topic out of request URLs and default HTTP logs.
        payload = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "maxlag": "5",
            **params,
        }
        async with client.stream("POST", WIKIPEDIA_API, data=payload) as response:
            response.raise_for_status()
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > 262144:
                    raise SourceUnavailable("source_size")
        result = json.loads(data)
        if not isinstance(result, dict) or "error" in result:
            raise SourceUnavailable("source_response")
        return result

    async def retrieve(self, resolution):
        if self.slots.locked():
            return None
        try:
            async with asyncio.timeout(settings.WIKIPEDIA_TIMEOUT_SECONDS):
                async with (
                    self.slots,
                    httpx.AsyncClient(
                        transport=self.transport,
                        timeout=3.5,
                        follow_redirects=False,
                        trust_env=False,
                        headers={"User-Agent": "FluiletEdTech/1.0"},
                    ) as client,
                ):
                    search = await self._query(
                        client,
                        {
                            "list": "search",
                            "srsearch": resolution.query,
                            "srlimit": "5",
                            "srnamespace": "0",
                        },
                    )
                    results = search.get("query", {}).get("search", [])[:5]
                    ids = [
                        str(row["pageid"])
                        for row in results
                        if isinstance(row, dict)
                        and type(row.get("pageid")) is int
                        and row["pageid"] > 0
                    ]
                    if not ids:
                        return None
                    extracts = await self._query(
                        client,
                        {
                            "prop": "extracts|pageprops|info",
                            "pageids": "|".join(ids),
                            "exintro": "1",
                            "explaintext": "1",
                            "exlimit": "5",
                        },
                    )
                    pages = extracts.get("query", {}).get("pages", [])
                    if isinstance(pages, dict):
                        pages = list(pages.values())
                    ranked = []
                    for page in pages:
                        if (
                            not isinstance(page, dict)
                            or str(page.get("pageid")) not in ids
                            or "disambiguation" in page.get("pageprops", {})
                        ):
                            continue
                        title, raw = page.get("title", ""), page.get("extract", "")
                        if not isinstance(title, str) or not isinstance(raw, str):
                            continue
                        text = clean_extract(raw)
                        if len(words(text)) < 20:
                            continue
                        score = _candidate_score(resolution, title, text)
                        if score is not None:
                            ranked.append(
                                (
                                    score,
                                    Article(
                                        title,
                                        text,
                                        resolution.category,
                                        "https://es.wikipedia.org/wiki/"
                                        + quote(title.replace(" ", "_"), safe=""),
                                        provider="wikipedia",
                                        revision_id=page.get("lastrevid")
                                        if isinstance(page.get("lastrevid"), int)
                                        else None,
                                    ),
                                )
                            )
                    return max(ranked, key=lambda row: row[0])[1] if ranked else None
        except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError, AttributeError):
            return None


wikipedia = WikipediaSource()


async def resolve_lesson(category, topic=None):
    resolution = resolve_topic(category, topic)
    article = await wikipedia.retrieve(resolution) if settings.WIKIPEDIA_ENABLED else None
    article = article or local_article(resolution)
    if article is None:
        raise SourceUnavailable("source_unavailable")
    return resolution.category, article

"""Baseline of the previously unmanaged schema. See docs/security.md before stamping."""

from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE TYPE user_role AS ENUM ('TUTOR', 'ADULTO_INDEPENDIENTE')")
    op.execute("CREATE TYPE difficulty_type AS ENUM ('DISLEXIA', 'TDAH', 'COMBINADO')")
    op.execute("CREATE TYPE visual_palette AS ENUM ('ALTO_CONTRASTE', 'SEPIA', 'ESTANDAR')")
    op.execute("CREATE TYPE document_type AS ENUM ('PDF', 'TXT')")
    op.execute(
        "CREATE TYPE document_status AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')"
    )
    op.execute(
        "\nCREATE TABLE users (\n\tid UUID NOT NULL, \n\temail VARCHAR(255) NOT NULL, \n\thashed_password VARCHAR(255) NOT NULL, \n\tfull_name VARCHAR(150) NOT NULL, \n\trole user_role NOT NULL, \n\tis_active BOOLEAN NOT NULL, \n\tis_verified BOOLEAN NOT NULL, \n\tfailed_login_attempts INTEGER NOT NULL, \n\tlocked_until TIMESTAMP WITH TIME ZONE, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id)\n)\n\n"
    )
    op.execute("CREATE UNIQUE INDEX ix_users_email ON users (email)")
    op.execute(
        "\nCREATE TABLE child_profiles (\n\tid UUID NOT NULL, \n\ttutor_id UUID NOT NULL, \n\tname VARCHAR(100) NOT NULL, \n\tbirth_date DATE NOT NULL, \n\ttipo_dificultad difficulty_type NOT NULL, \n\tnivel_simplificacion_nlp INTEGER NOT NULL, \n\tpaleta_visual visual_palette NOT NULL, \n\ttamano_fuente INTEGER NOT NULL, \n\tinterlineado FLOAT NOT NULL, \n\tpin_hash VARCHAR(255), \n\tis_active BOOLEAN NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_nivel_nlp_rango CHECK (nivel_simplificacion_nlp BETWEEN 1 AND 5), \n\tCONSTRAINT ck_tamano_fuente_rango CHECK (tamano_fuente BETWEEN 14 AND 28), \n\tCONSTRAINT ck_interlineado_rango CHECK (interlineado BETWEEN 1.5 AND 2.5), \n\tFOREIGN KEY(tutor_id) REFERENCES users (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute("CREATE INDEX ix_child_profiles_tutor_id ON child_profiles (tutor_id)")
    op.execute(
        "\nCREATE TABLE documents (\n\tid UUID NOT NULL, \n\towner_id UUID NOT NULL, \n\tfile_name VARCHAR(255) NOT NULL, \n\tfile_type document_type NOT NULL, \n\tfile_size_bytes INTEGER NOT NULL, \n\tstorage_path VARCHAR(500) NOT NULL, \n\tstatus document_status NOT NULL, \n\tuploaded_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_tamano_max_10mb CHECK (file_size_bytes > 0 AND file_size_bytes <= 10485760), \n\tFOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute("CREATE INDEX ix_documents_owner_id ON documents (owner_id)")
    op.execute(
        "\nCREATE TABLE refresh_tokens (\n\tid UUID NOT NULL, \n\tuser_id UUID NOT NULL, \n\ttoken_hash VARCHAR(255) NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\trevoked BOOLEAN NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute("CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens (user_id)")
    op.execute("CREATE UNIQUE INDEX ix_refresh_tokens_token_hash ON refresh_tokens (token_hash)")
    op.execute(
        "\nCREATE TABLE child_library_items (\n\tid UUID NOT NULL, \n\tchild_id UUID NOT NULL, \n\tdocument_id UUID NOT NULL, \n\tassigned_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_child_document UNIQUE (child_id, document_id), \n\tFOREIGN KEY(child_id) REFERENCES child_profiles (id) ON DELETE CASCADE, \n\tFOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE\n)\n\n"
    )
    op.execute(
        "\nCREATE TABLE reading_sessions (\n\tid UUID NOT NULL, \n\tchild_id UUID NOT NULL, \n\tdocument_id UUID, \n\tstarted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tended_at TIMESTAMP WITH TIME ZONE, \n\tduration_seconds INTEGER NOT NULL, \n\tprogress_percentage NUMERIC(5, 2) NOT NULL, \n\tcompleted BOOLEAN NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_progreso_rango CHECK (progress_percentage BETWEEN 0 AND 100), \n\tFOREIGN KEY(child_id) REFERENCES child_profiles (id) ON DELETE CASCADE, \n\tFOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE SET NULL\n)\n\n"
    )
    op.execute("CREATE INDEX ix_reading_sessions_child_id ON reading_sessions (child_id)")


def downgrade():
    op.drop_table("reading_sessions")
    op.drop_table("child_library_items")
    op.drop_table("refresh_tokens")
    op.drop_table("documents")
    op.drop_table("child_profiles")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS user_role")
    op.execute("DROP TYPE IF EXISTS difficulty_type")
    op.execute("DROP TYPE IF EXISTS visual_palette")
    op.execute("DROP TYPE IF EXISTS document_type")
    op.execute("DROP TYPE IF EXISTS document_status")

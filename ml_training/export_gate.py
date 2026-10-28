"""Publish the frozen v2.3 gate and measured structural diagnostics."""

from ml_training.export_joint import package

if __name__ == "__main__":
    package("v2.3")

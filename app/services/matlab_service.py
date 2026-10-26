"""Optional MATLAB Engine integration for the FastAPI backend."""
from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any

from app.config import MATLAB_SCRIPTS_DIR


class MatlabUnavailableError(RuntimeError):
    """MATLAB or its Python engine is unavailable."""


class MatlabService:
    """Own a MATLAB session and expose vetted application functions."""

    def __init__(self, scripts_dir: Path = MATLAB_SCRIPTS_DIR) -> None:
        self.scripts_dir = scripts_dir
        self._engine: Any | None = None
        self._lock = Lock()

    def _get_engine(self) -> Any:
        with self._lock:
            if self._engine is not None:
                return self._engine
            if not self.scripts_dir.is_dir():
                raise MatlabUnavailableError(f"MATLAB scripts directory does not exist: {self.scripts_dir}")
            try:
                import matlab.engine  # type: ignore[import-not-found]
                engine = matlab.engine.start_matlab()
                engine.addpath(str(self.scripts_dir), nargout=0)
            except ImportError as exc:
                raise MatlabUnavailableError("MATLAB Engine for Python is not installed. Install it from <MATLABROOT>/extern/engines/python.") from exc
            except Exception as exc:
                raise MatlabUnavailableError(f"Could not start MATLAB: {exc}") from exc
            self._engine = engine
            return engine

    def ingredient_score(self, values: list[float]) -> dict[str, float | str]:
        try:
            import matlab  # type: ignore[import-not-found]
            mean_score, normalized_score, risk_band = self._get_engine().ingredient_score(matlab.double([values]), nargout=3)
        except MatlabUnavailableError:
            raise
        except ImportError as exc:
            raise MatlabUnavailableError("MATLAB Engine for Python is not installed.") from exc
        except Exception as exc:
            raise MatlabUnavailableError(f"MATLAB calculation failed: {exc}") from exc
        return {"mean_score": float(mean_score), "normalized_score": float(normalized_score), "risk_band": str(risk_band)}

    def close(self) -> None:
        with self._lock:
            if self._engine is not None:
                self._engine.quit()
                self._engine = None


matlab_service = MatlabService()

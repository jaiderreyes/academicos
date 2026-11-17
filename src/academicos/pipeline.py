from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import stat
import tempfile
import time
from zipfile import ZipFile

from .validation import LocalSimilarityIndex, file_hash
from .catalog import Catalog
from .storage import atomic_write, safe_path, workspace_lock
from .tracking import RunTracker
from .reports import export_reports


@dataclass(frozen=True)
class Limits:
    max_files: int = 2000
    max_bytes: int = 500 * 1024 * 1024
    max_depth: int = 3


class Pipeline:
    """Procesa documentos sin modificar originales y con presupuesto global ZIP."""

    def __init__(self, converter, limits=None, progress_callback=None):
        self.converter = converter
        self.progress_callback = progress_callback
        self.limits = limits or Limits()
        self.rows = []
        self.expanded_files = 0
        self.expanded_bytes = 0
        self.converter_key = str(getattr(converter, "cache_key",
            type(converter).__module__ + ":" + type(converter).__qualname__)) + ":pipeline-3"

    def run(self, source: Path, output: Path):
        source, output = source.expanduser().resolve(), output.expanduser().resolve()
        if not source.is_dir():
            raise ValueError("La entrada debe ser una carpeta existente")
        if output == source or source.is_relative_to(output):
            raise ValueError("La salida no puede ser la entrada ni una carpeta que la contenga")
        self.rows = []
        self.similarity_index = LocalSimilarityIndex()
        self.expanded_files = self.expanded_bytes = 0
        self.source_root = str(source)
        self.output_root = output
        self.attempt_id = None
        output.mkdir(parents=True, exist_ok=True)
        with workspace_lock(output):
            self.catalog = Catalog(output)
            try:
                self.run_id = self.catalog.start_run(str(source), self.converter_key)
                report = safe_path(output, output / ("reporte-" + self.run_id + ".json"))
                self.tracker = RunTracker(output, self.run_id, str(source), self.progress_callback)
                try:
                    candidates = []
                    for path in sorted(source.rglob("*")):
                        if path.is_symlink() or path.is_relative_to(output):
                            continue
                        if any(parent.is_symlink() for parent in path.parents if parent != source):
                            continue
                        if path.is_file():
                            candidates.append((path, path.relative_to(source)))
                    self.tracker.discovered([relative for _, relative in candidates], scan_complete=True)
                    self.tracker.stage("preparando")
                    for path, relative in candidates:
                        self._visit(path, relative, output, 0)
                except BaseException:
                    self.catalog.finish_run(self.run_id, "interrupted")
                    self.tracker.finish("interrupted")
                    export_reports(output, self.run_id)
                    raise
                else:
                    self.tracker.stage("generando_reportes")
                    self.catalog.finish_run(self.run_id, "completed")
                    export_reports(output, self.run_id)
                    self.tracker.finish("completed")
            finally:
                self.catalog.close()
        return report, self.rows

    def _visit(self, path, relative, output, depth):
        suffix = path.suffix.lower()
        if suffix == ".zip":
            failed = False
            self.tracker.stage("extrayendo_zip", relative)
            try:
                self._archive(path, relative, output, depth)
            except Exception as exc:
                failed = True
                self._record(relative, "error_zip", error=str(exc))
            except BaseException:
                failed = True
                raise
            finally:
                self.tracker.archive_finished(failed)
            return
        if suffix not in {".pdf", ".docx"}:
            if suffix in {".doc", ".rar", ".7z"}:
                self._record(relative, "no_soportado")
            return
        self._document(path, relative, output)

    def _document(self, path, relative, output):
        self.attempt_id = self.catalog.start_attempt(self.run_id, relative.as_posix())
        self.document_started = time.monotonic()
        self.tracker.stage("leyendo_hash", relative)
        try:
            self._process_document(path, relative, output)
        finally:
            self.attempt_id = None

    def _process_document(self, path, relative, output):
        metadata = {"sha256_before": None, "sha256_after": None,
                    "integrity": "no_verificada", "duplicate_of": None,
                    "local_comparison": {"status": "no_evaluado", "matches": []},
                    "academic_originality": "no_evaluada", "external_sources": "no_consultadas",
                    "converter_key": self.converter_key}
        try:
            before = file_hash(path)
            metadata["sha256"] = metadata["sha256_before"] = before
            location, duplicate = self.catalog.observe(self.source_root, relative.as_posix(), before)
            if duplicate:
                metadata["duplicate_of"] = duplicate["first_source"]
                metadata["duplicate_root"] = duplicate["first_root"]
        except Exception as exc:
            self._record(relative, "error_lectura", error=str(exc), **metadata)
            return
        text, conversion, error = None, None, None
        status = "convertido"
        key = sha256(json.dumps([before, path.suffix.lower(), self.converter_key]).encode()).hexdigest()
        metadata["cache_key"] = key
        try:
            target = safe_path(output, output / "documentos" / relative.parent / (relative.name + ".md"))
            self.tracker.stage("buscando_cache", relative)
            conversion = self.catalog.lookup(key)
            if conversion:
                artifact = safe_path(output, output / conversion["artifact"])
                if not artifact.is_file() or file_hash(artifact) != conversion["output_sha"]:
                    conversion = None
            if conversion is None:
                self.tracker.stage("convirtiendo", relative)
                text = self.converter.convert(path)
                if not text or not text.strip():
                    status, error = "sin_texto", "Revisar documento; puede necesitar OCR"
        except Exception as exc:
            status, error = "error_conversion", str(exc)
        self.tracker.stage("verificando_integridad", relative)
        try:
            after = file_hash(path)
            metadata["sha256_after"] = after
            metadata["integrity"] = "verificada" if before == after else "fallida"
            if before != after:
                self._record(relative, "error_integridad", error="El documento cambió durante el procesamiento", **metadata)
                return
        except Exception as exc:
            self._record(relative, "error_integridad", error=str(exc), **metadata)
            return
        if error:
            if location["current_conversion_id"] is not None:
                metadata["previous_output_preserved"] = True
            self._record(relative, status, error=error, **metadata)
            return
        reused = conversion is not None
        self.tracker.stage("publicando", relative)
        try:
            if conversion is None:
                data = (text.rstrip() + "\n").encode("utf-8")
                output_sha = sha256(data).hexdigest()
                artifact_relative = Path("artefactos") / (output_sha + ".md")
                artifact = safe_path(output, output / artifact_relative)
                if not artifact.is_file() or file_hash(artifact) != output_sha:
                    atomic_write(artifact, data)
                conversion = self.catalog.add_conversion(key, before, self.converter_key,
                    path.suffix.lower(), artifact_relative.as_posix(), output_sha)
            else:
                artifact = safe_path(output, output / conversion["artifact"])
                data = artifact.read_bytes()
                if sha256(data).hexdigest() != conversion["output_sha"]:
                    raise ValueError("El artefacto cambió antes de su publicación; reintente")
            metadata["artifact"] = conversion["artifact"]
            metadata["conversion_id"] = conversion["id"]
            metadata["output_sha256"] = conversion["output_sha"]
            current_sha = file_hash(target) if target.exists() else None
            # Una vista solo se sustituye si es la registrada o coincide con el resultado.
            if current_sha is not None and current_sha not in {
                    conversion["output_sha"], location["current_output_sha"]}:
                self._record(relative, "conflicto_salida", existing_output=str(target),
                    error="Salida no reconocida o editada manualmente; se conserva", **metadata)
                return
            if current_sha != conversion["output_sha"]:
                atomic_write(target, data)
            self.catalog.bind(location, conversion, target)
            if reused:
                if current_sha == conversion["output_sha"]:
                    status = "omitido_sin_cambios" if location["current_conversion_id"] == conversion["id"] else "reutilizado"
                else:
                    status = "restaurado" if location["current_conversion_id"] == conversion["id"] else "reutilizado"
            else:
                status = "actualizado" if location["current_conversion_id"] is not None else "convertido"
                metadata["local_comparison"] = self.similarity_index.compare_and_add(relative.as_posix(), text)
            metadata["output"] = str(target)
        except Exception as exc:
            self._record(relative, "error_conversion", error=str(exc), **metadata)
            return
        self._record(relative, status, **metadata)

    def _archive(self, path, relative, output, depth):
        if depth >= self.limits.max_depth:
            raise ValueError("Límite de profundidad ZIP alcanzado")
        with ZipFile(path) as archive, tempfile.TemporaryDirectory(prefix="academicos-") as tmp:
            entries = archive.infolist()
            pending_bytes = 0
            pending_count = 0
            seen = set()
            # Validar todo el archivo antes de extraer el primer elemento.
            for entry in entries:
                name = PurePosixPath(entry.filename)
                if (name.is_absolute() or ".." in name.parts or "\\" in entry.filename
                        or ":" in entry.filename or not name.parts):
                    raise ValueError("Ruta ZIP insegura")
                if entry.filename in seen:
                    raise ValueError("Entrada ZIP duplicada")
                seen.add(entry.filename)
                mode = entry.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise ValueError("Enlace simbólico dentro del ZIP")
                if entry.flag_bits & 1:
                    raise ValueError("ZIP protegido con contraseña")
                pending_count += 1
                pending_bytes += entry.file_size
            if self.expanded_files + pending_count > self.limits.max_files:
                raise ValueError("Límite global de entradas ZIP alcanzado")
            if self.expanded_bytes + pending_bytes > self.limits.max_bytes:
                raise ValueError("Límite global de bytes ZIP alcanzado")
            self.expanded_files += pending_count
            extracted = []
            for index, entry in enumerate(entries):
                if entry.is_dir():
                    continue
                # Nombres internos opacos: nunca se usan rutas del ZIP al escribir temporales.
                destination = Path(tmp) / (str(index) + PurePosixPath(entry.filename).suffix)
                with archive.open(entry) as src, destination.open("xb") as dst:
                    while chunk := src.read(1024 * 1024):
                        self.expanded_bytes += len(chunk)
                        if self.expanded_bytes > self.limits.max_bytes:
                            raise ValueError("Límite real de extracción alcanzado")
                        dst.write(chunk)
                child = relative / "__zip__" / Path(entry.filename)
                extracted.append((destination, child))
            self.tracker.discovered([child for _, child in extracted])
            for destination, child in extracted:
                self._visit(destination, child, output, depth + 1)

    def _record(self, relative, status, **extra):
        if self.attempt_id is not None:
            extra["duration_seconds"] = round(time.monotonic() - self.document_started, 6)
        row = {"source": relative.as_posix(), "status": status, **extra}
        self.catalog.record(self.run_id, row, self.attempt_id)
        self.rows.append(row)
        self.tracker.record(row)

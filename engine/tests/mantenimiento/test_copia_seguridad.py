import subprocess
from datetime import datetime, timezone

import pytest

from app import config
from app.mantenimiento import copia_seguridad as cs


def test_parametros_desde_url_completa():
    parametros = cs.parametros_desde_url("postgresql+psycopg://adif:secreta@postgres:5432/adif")

    assert parametros.host == "postgres"
    assert parametros.port == "5432"
    assert parametros.user == "adif"
    assert parametros.password == "secreta"
    assert parametros.dbname == "adif"


def test_parametros_desde_url_usa_valores_por_defecto_si_faltan():
    parametros = cs.parametros_desde_url("postgresql://localhost/")

    assert parametros.host == "localhost"
    assert parametros.port == "5432"
    assert parametros.dbname == "adif"


def test_nombre_archivo_es_ordenable_cronologicamente():
    momento = datetime(2026, 9, 6, 13, 5, 30, tzinfo=timezone.utc)

    nombre = cs.nombre_archivo(momento)

    assert nombre == "adif_20260906_130530.dump"


def test_listar_copias_ordena_mas_reciente_primero(tmp_path):
    (tmp_path / "adif_20260101_000000.dump").write_bytes(b"x")
    (tmp_path / "adif_20260301_000000.dump").write_bytes(b"x")
    (tmp_path / "adif_20260201_000000.dump").write_bytes(b"x")
    # Ruido que no debe colarse: otro tipo de fichero y un subdirectorio.
    (tmp_path / "otra_cosa.txt").write_bytes(b"x")
    (tmp_path / "adif_carpeta.dump").mkdir()

    copias = cs.listar_copias(str(tmp_path))

    assert [p.name for p in copias] == [
        "adif_20260301_000000.dump",
        "adif_20260201_000000.dump",
        "adif_20260101_000000.dump",
    ]


def test_listar_copias_directorio_inexistente(tmp_path):
    assert cs.listar_copias(str(tmp_path / "no_existe")) == []


def test_purgar_copias_antiguas_conserva_solo_la_retencion(tmp_path):
    for nombre in ["adif_20260101_000000.dump", "adif_20260201_000000.dump", "adif_20260301_000000.dump"]:
        (tmp_path / nombre).write_bytes(b"x")

    eliminadas = cs.purgar_copias_antiguas(retencion=2, directorio=str(tmp_path))

    assert eliminadas == ["adif_20260101_000000.dump"]
    restantes = {p.name for p in tmp_path.iterdir()}
    assert restantes == {"adif_20260201_000000.dump", "adif_20260301_000000.dump"}


def test_purgar_copias_antiguas_sin_sobrantes_no_borra_nada(tmp_path):
    (tmp_path / "adif_20260101_000000.dump").write_bytes(b"x")

    eliminadas = cs.purgar_copias_antiguas(retencion=14, directorio=str(tmp_path))

    assert eliminadas == []
    assert (tmp_path / "adif_20260101_000000.dump").exists()


def _indice_argumento(args: list[str], nombre: str) -> str:
    return args[args.index(nombre) + 1]


def test_ejecutar_copia_seguridad_exito(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "backup_dir", str(tmp_path))
    monkeypatch.setattr(config.settings, "backup_retencion", 14)
    monkeypatch.setattr(
        config.settings, "database_url", "postgresql+psycopg://adif:adif@postgres:5432/adif"
    )

    def pg_dump_falso(args, env, capture_output, text, timeout):
        assert args[0] == "pg_dump"
        assert env["PGHOST"] == "postgres"
        assert env["PGPASSWORD"] == "adif"
        destino = _indice_argumento(args, "--file")
        with open(destino, "wb") as f:
            f.write(b"contenido de prueba del volcado")
        return subprocess.CompletedProcess(args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", pg_dump_falso)

    resultado = cs.ejecutar_copia_seguridad(db=None, trabajo=None)

    assert resultado["tamano_bytes"] == len(b"contenido de prueba del volcado")
    assert resultado["copias_conservadas"] == 1
    assert resultado["copias_eliminadas"] == []
    archivos = list(tmp_path.iterdir())
    assert len(archivos) == 1
    assert archivos[0].name == resultado["archivo"]


def test_ejecutar_copia_seguridad_purga_las_mas_antiguas(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "backup_dir", str(tmp_path))
    monkeypatch.setattr(config.settings, "backup_retencion", 2)
    monkeypatch.setattr(
        config.settings, "database_url", "postgresql+psycopg://adif:adif@postgres:5432/adif"
    )
    for nombre in ["adif_20260101_000000.dump", "adif_20260102_000000.dump"]:
        (tmp_path / nombre).write_bytes(b"x")

    def pg_dump_falso(args, env, capture_output, text, timeout):
        destino = _indice_argumento(args, "--file")
        with open(destino, "wb") as f:
            f.write(b"nuevo")
        return subprocess.CompletedProcess(args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", pg_dump_falso)

    resultado = cs.ejecutar_copia_seguridad(db=None, trabajo=None)

    assert resultado["copias_conservadas"] == 2
    assert resultado["copias_eliminadas"] == ["adif_20260101_000000.dump"]
    assert not (tmp_path / "adif_20260101_000000.dump").exists()
    assert (tmp_path / "adif_20260102_000000.dump").exists()


def test_ejecutar_copia_seguridad_fallo_no_deja_archivo_a_medias(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "backup_dir", str(tmp_path))
    monkeypatch.setattr(
        config.settings, "database_url", "postgresql+psycopg://adif:adif@postgres:5432/adif"
    )

    def pg_dump_falso(args, env, capture_output, text, timeout):
        destino = _indice_argumento(args, "--file")
        with open(destino, "wb") as f:
            f.write(b"a medias, la conexion se corto")
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="conexión perdida a mitad de volcado")

    monkeypatch.setattr(subprocess, "run", pg_dump_falso)

    with pytest.raises(RuntimeError, match="pg_dump falló"):
        cs.ejecutar_copia_seguridad(db=None, trabajo=None)

    assert list(tmp_path.iterdir()) == []

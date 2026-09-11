from pathlib import Path

from rosa import datos as D


def test_resumen_csv_da_mediana_cuartiles_y_signos(tmp_path: Path):
    f = tmp_path / "t.csv"
    f.write_text("id,brecha,grupo\n1,2.0,a\n2,-1.0,b\n3,3.0,a\n4,NA,a\n5,0,b\n6,4.5,a\n", encoding="utf-8")
    resumen, muestra = D.resumir(f)
    assert "6 filas, 3 columnas" in resumen
    assert "brecha (numerica)" in resumen and "mediana=" in resumen and "IC95" in resumen
    assert "positivos=3, negativos=1, ceros=1, faltantes=1" in resumen
    assert "grupo (categorica)" in resumen and "a=4" in resumen
    assert muestra.startswith("id,brecha,grupo")


def test_rutas_seguras():
    r = D.ruta_de("hip-1", "../../etc/passwd")
    assert r is not None and r.name == "passwd" and "hip-1" in str(r.parent)
    assert D.ruta_de("hip-1", "") is None

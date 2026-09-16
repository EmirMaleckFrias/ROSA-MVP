"""Comprueba la distribución del modelo de mundo sin tocar la API real.

Con Vite en localhost:5174:
uv run --with playwright python scripts/probar_mundo_columnas.py
"""

import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    salida = Path(tempfile.mkdtemp(prefix="rosa-mundo-columnas-"))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900}, reduced_motion="reduce")
        page.route("**/api/**", lambda r: r.fulfill(status=503, body="{}", content_type="application/json"))
        page.goto("http://localhost:5174")
        page.wait_for_load_state("networkidle")
        page.evaluate("""async () => {
          const {default: React} = await import('/node_modules/.vite/deps/react.js');
          const {default: DOM} = await import('/node_modules/.vite/deps/react-dom_client.js');
          const {ModeloDeMundo} = await import('/src/pantallas/ModeloDeMundo.tsx');
          const {estadoDeMuestra} = await import('/src/datos/muestra.ts');
          const estado = estadoDeMuestra();
          const inv = estado.investigaciones[0];
          const hecho = estado.hechos.find(h => h.investigacionId === inv.id);
          estado.hechos = Array.from({length: 12}, (_, i) => ({...hecho,
            id: 'qa-' + i, estado: 'sabido',
            enunciado: 'Hecho de prueba ' + i + '. ' + hecho.enunciado.repeat(i % 3 + 1)}));
          estado.hechos.push({...hecho, id: 'qa-abierto', estado: 'abierto'});
          const div = document.createElement('div'); document.body.replaceChildren(div);
          DOM.createRoot(div).render(React.createElement(ModeloDeMundo, {estado, inv, ahora: Date.now()}));
        }""")
        page.wait_for_selector(".mundo-tarjetas > li")
        page.locator(".mundo-columnas").scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        tarjetas = page.locator(".mundo-tarjetas").first.locator(":scope > li")
        assert tarjetas.count() == 12
        cajas = [tarjetas.nth(i).bounding_box() for i in range(12)]
        for i in range(0, 12, 2):
            assert abs(cajas[i]["y"] - cajas[i + 1]["y"]) < 2
            assert cajas[i + 1]["x"] > cajas[i]["x"] + cajas[i]["width"]
        page.screenshot(path=str(salida / "escritorio.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(300)
        cajas = [tarjetas.nth(i).bounding_box() for i in range(12)]
        for i in range(1, 12):
            assert abs(cajas[i]["x"] - cajas[0]["x"]) < 2
            assert cajas[i]["y"] >= cajas[i - 1]["y"] + cajas[i - 1]["height"]
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(salida / "movil.png"), full_page=True)
        browser.close()
    print(f"12 tarjetas: dos columnas hasta el final en escritorio, una en móvil. Capturas: {salida}")


if __name__ == "__main__":
    main()

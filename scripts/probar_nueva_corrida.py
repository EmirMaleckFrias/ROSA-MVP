"""Prueba el formulario con Vite y datos simulados; no inicia corridas reales."""
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    salida = Path(tempfile.mkdtemp(prefix="rosa-nueva-corrida-"))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1000, "height": 900}, reduced_motion="reduce")
        page.route("**/api/**", lambda r: r.fulfill(status=503, body="{}", content_type="application/json"))
        page.goto("http://localhost:5174")
        page.wait_for_load_state("networkidle")
        page.evaluate("""async () => {
          const {default: React} = await import('/node_modules/.vite/deps/react.js');
          const {default: DOM} = await import('/node_modules/.vite/deps/react-dom_client.js');
          const {Corrida} = await import('/src/pantallas/Corrida.tsx');
          const {estadoDeMuestra} = await import('/src/datos/muestra.ts');
          // Vite puede tener la versión con sello HMR y la URL sin sello.
          const urls = new Set(performance.getEntriesByType('resource').map(r => r.name).filter(u => new URL(u).pathname === '/src/datos/almacen.ts'));
          urls.add('/src/datos/almacen.ts');
          for (const url of urls) {
            const {acciones} = await import(url);
            acciones.iniciarCorrida = (id, parada) => { window.paradaEnviada = parada; };
          }
          const estado = estadoDeMuestra();
          estado.conexion = 'conectado';
          const inv = estado.investigaciones[0];
          estado.corridas.filter(c => c.investigacionId === inv.id).forEach(c => {
            c.estado = 'terminada';
            c.parada = {horas: 1.05, iteraciones: null, llamadas: 800, texto: ''};
          });
          const div = document.createElement('div'); document.body.replaceChildren(div);
          DOM.createRoot(div).render(React.createElement(Corrida, {estado, inv, ahora: Date.now(), irA: () => {}}));
        }""")
        page.get_by_role("button", name="Nueva corrida", exact=True).click()
        form = page.locator(".nueva-corrida")
        assert form.get_by_text("Llamadas al modelo", exact=True).count() == 0
        tiempo = form.get_by_label("Tiempo", exact=True)
        unidad = form.get_by_label("Unidad de tiempo", exact=True)
        assert tiempo.input_value() == "1.05"
        assert tiempo.evaluate("el => el.validity.valid")
        tiempo.fill("10")
        unidad.select_option("minutos")
        assert "10 minutos" in form.get_by_role("button", name="Empezar:").inner_text()
        certeza = form.get_by_label("Parar al llegar a certeza", exact=True)
        assert certeza.bounding_box()["width"] >= 220
        form.screenshot(path=str(salida / "escritorio.png"))
        for valor, tipo, horas in [("10", "minutos", 10 / 60), ("1.5", "horas", 1.5), ("2", "dias", 48)]:
            tiempo.fill(valor)
            unidad.select_option(tipo)
            assert form.evaluate("el => el.checkValidity()"), form.locator(":invalid").evaluate_all("els => els.map(el => [el.outerHTML, el.validationMessage])")
            form.get_by_role("button", name="Empezar:").click()
            enviada = page.evaluate("window.paradaEnviada")
            assert enviada is not None, {"valor": valor, "tipo": tipo, "formulario_abierto": form.count()}
            assert abs(enviada["horas"] - horas) < 1e-12
            assert enviada["llamadas"] is None
            page.get_by_role("button", name="Nueva corrida", exact=True).click()
        page.set_viewport_size({"width": 390, "height": 844})
        form.scroll_into_view_if_needed()
        assert form.evaluate("el => el.scrollWidth <= el.clientWidth")
        assert certeza.bounding_box()["width"] >= 220
        form.screenshot(path=str(salida / "movil.png"))
        browser.close()
    print(f"Conversión, eliminación del límite oculto y CSS verificados. Capturas: {salida}")


if __name__ == "__main__":
    main()

import base64
import argparse
import json
import webbrowser
import zlib
from pathlib import Path
import numpy as np
import plotly.graph_objects as go


def gerar_visualizacao_3d(
    caminho_npz: str = None,
    arquivo_saida: str = "index.html",
    abrir_navegador: bool = True,
):
    base_dir = Path(__file__).parent
    if caminho_npz is None:
        caminho_npz = base_dir / "modelo_reservatorio_3d.npz"
    else:
        caminho_npz = Path(caminho_npz)

    dados = np.load(str(caminho_npz))
    x = dados["x_m"] if "x_m" in dados else dados["x"]
    y = dados["y_m"] if "y_m" in dados else dados["y"]
    z = dados["z_m"] if "z_m" in dados else dados["z"]
    facies_labels = (
        np.asarray(dados["facies_names"]).astype(str)
        if "facies_names" in dados
        else None
    )
    architecture_labels = (
        np.asarray(dados["architecture_names"]).astype(str)
        if "architecture_names" in dados
        else None
    )

    category_names = {
        "facies": facies_labels,
        "architecture": architecture_labels,
    }
    category_offsets = {"facies": 1, "architecture": 0}

    def labels_for_category(prop, values):
        codes = np.rint(values).astype(int)
        labels = codes.astype(str).astype(object)
        names = category_names.get(prop)
        if names is None:
            return labels
        offset = category_offsets[prop]
        indices = codes - offset
        valid = (indices >= 0) & (indices < len(names))
        labels[valid] = names[indices[valid]]
        return labels

    # Malhas para fatias e volume
    X_z, Y_z = np.meshgrid(x, y)
    Y_x, Z_x = np.meshgrid(y, z, indexing="ij")
    X_y, Z_y = np.meshgrid(x, z, indexing="ij")

    # Amostragem otimizada para o volume 3D web
    x_sub = x[::2]
    y_sub = y[::2]
    Y_vol, X_vol, Z_vol = np.meshgrid(y_sub, x_sub, z, indexing="ij")

    mid_z = len(z) // 2
    mid_x = len(x) // 2
    mid_y = len(y) // 2

    property_specs = {
        "porosity": {"keys": ("phi", "porosity"), "label": "Porosidade (phi)", "colorscale": "Viridis", "decimals": 4},
        "permeability": {"keys": ("K", "permeability_mD", "permeability"), "label": "Permeabilidade (K)", "colorscale": "Turbo", "decimals": 2},
        "vertical_permeability": {"keys": ("Kz",), "label": "Permeabilidade vertical (Kz)", "colorscale": "Turbo", "decimals": 2},
        "shale_volume": {"keys": ("Vsh",), "label": "Volume de folhelho (Vsh)", "colorscale": "Viridis", "decimals": 3},
        "vp": {"keys": ("Vp", "vp_ms"), "label": "Velocidade P (Vp)", "colorscale": "Turbo", "decimals": 2},
        "vs": {"keys": ("Vs", "vs_ms"), "label": "Velocidade S (Vs)", "colorscale": "Turbo", "decimals": 2},
        "density": {"keys": ("rho", "density_gcc"), "label": "Densidade (rho)", "colorscale": "Viridis", "decimals": 3},
        "gamma_ray": {"keys": ("GR",), "label": "Raios gama (GR)", "colorscale": "Viridis", "decimals": 2},
        "resistivity": {"keys": ("resistivity",), "label": "Resistividade", "colorscale": "Turbo", "decimals": 2},
        "water_saturation": {"keys": ("Sw", "water_saturation"), "label": "Saturação de água (Sw)", "colorscale": "Viridis", "decimals": 3},
        "acoustic_impedance": {"keys": ("Ip", "acoustic_impedance"), "label": "Impedância P (Ip)", "colorscale": "Turbo", "decimals": 2},
        "shear_impedance": {"keys": ("Is",), "label": "Impedância S (Is)", "colorscale": "Turbo", "decimals": 2},
        "normalized_acoustic_impedance": {"keys": ("Ip_norm",), "label": "Impedância P normalizada", "colorscale": "RdBu", "decimals": 3},
        "normalized_shear_impedance": {"keys": ("Is_norm",), "label": "Impedância S normalizada", "colorscale": "RdBu", "decimals": 3},
        "facies": {"keys": ("facies",), "label": "Fácies", "colorscale": "Portland", "decimals": 0, "categorical": True},
        "unit": {"keys": ("unit",), "label": "Unidade", "colorscale": "Viridis", "decimals": 0, "categorical": True},
        "architecture": {"keys": ("architecture",), "label": "Arquitetura", "colorscale": "Portland", "decimals": 0, "categorical": True},
    }
    propriedades = [
        prop for prop, spec in property_specs.items()
        if any(key in dados for key in spec["keys"])
    ]
    cmaps = {prop: property_specs[prop]["colorscale"] for prop in propriedades}

    # Arredondamento numérico para reduzir tamanho do JSON para web/GitHub Pages
    data_dict = {}
    for p in propriedades:
        source_key = next(key for key in property_specs[p]["keys"] if key in dados)
        val = dados[source_key].astype(np.float32)
        if val.shape == (len(z), len(y), len(x)):
            val = np.transpose(val, (1, 2, 0))
        elif val.shape == (len(x), len(y), len(z)) and val.shape != (len(y), len(x), len(z)):
            val = np.transpose(val, (1, 0, 2))
        data_dict[p] = np.round(val, property_specs[p]["decimals"])

    browser_properties = {}
    compressed_fields = {}
    for prop in propriedades:
        val = data_dict[prop]
        category_codes = np.unique(np.rint(val).astype(int)) if property_specs[prop].get("categorical") else []
        category_names_for_prop = category_names.get(prop)
        browser_properties[prop] = {
            "label": property_specs[prop]["label"],
            "minimum": float(np.nanmin(val)),
            "maximum": float(np.nanmax(val)),
            "colorscale": property_specs[prop]["colorscale"],
            "categorical": bool(property_specs[prop].get("categorical")),
            "categoryNames": category_names_for_prop.tolist() if category_names_for_prop is not None else None,
            "categoryOffset": category_offsets.get(prop, 0),
            "tickvals": category_codes.tolist() if len(category_codes) else [],
            "ticktext": labels_for_category(prop, category_codes).tolist() if len(category_codes) else [],
        }
        values_bytes = np.ascontiguousarray(val, dtype="<f4").tobytes()
        compressed_fields[prop] = base64.b64encode(zlib.compress(values_bytes)).decode("ascii")

    idx_y_list = list(range(0, len(y), 2))
    if (len(y) - 1) not in idx_y_list:
        idx_y_list.append(len(y) - 1)
    idx_x_list = list(range(0, len(x), 2))
    if (len(x) - 1) not in idx_x_list:
        idx_x_list.append(len(x) - 1)
    active_y = idx_y_list.index(mid_y if mid_y in idx_y_list else idx_y_list[len(idx_y_list) // 2])
    active_x = idx_x_list.index(mid_x if mid_x in idx_x_list else idx_x_list[len(idx_x_list) // 2])

    fig = go.Figure()

    # Cada propriedade recebe 4 traces:
    # 0: Fatia Z (Profundidade / Horizontal)
    # 1: Fatia X (Crossline / Vertical)
    # 2: Fatia Y (Inline / Vertical)
    # 3: Volume 3D (Nuvem volumétrica)
    for i, prop in enumerate(propriedades[:1]):
        val = data_dict[prop]
        vmin, vmax = float(np.nanmin(val)), float(np.nanmax(val))
        ativo = (i == 0)
        spec = property_specs[prop]
        colorbar = dict(title=spec["label"], x=0.86, y=0.58, len=0.52)
        hover_z = {}
        hover_x = {}
        hover_y = {}
        hover_volume = {}
        if spec.get("categorical"):
            category_codes = np.unique(np.rint(val).astype(int))
            colorbar.update(
                title=spec["label"],
                tickmode="array",
                tickvals=category_codes,
                ticktext=labels_for_category(prop, category_codes),
            )
            hover_template = (
                f"x: %{{x}}<br>y: %{{y}}<br>z: %{{z}}<br>{spec['label']}: "
                "%{customdata}<extra></extra>"
            )
            hover_z = {
                "customdata": labels_for_category(prop, val[:, :, mid_z]),
                "hovertemplate": hover_template,
            }
            hover_x = {
                "customdata": labels_for_category(prop, val[:, mid_x, :]),
                "hovertemplate": hover_template,
            }
            hover_y = {
                "customdata": labels_for_category(prop, val[mid_y, :, :]),
                "hovertemplate": hover_template,
            }
            hover_volume = {
                "customdata": labels_for_category(prop, val[::2, ::2, :]).flatten(),
                "hovertemplate": hover_template,
            }

        # 1. Fatia Z (Horizontal)
        fig.add_trace(
            go.Surface(
                x=X_z,
                y=Y_z,
                z=np.full_like(X_z, z[mid_z]),
                surfacecolor=val[:, :, mid_z],
                colorscale=cmaps[prop],
                name="Fatia Z",
                legendgroup=prop,
                cmin=vmin,
                cmax=vmax,
                colorbar=colorbar,
                visible=ativo,
                showscale=True,
                **hover_z,
            )
        )

        # 2. Fatia X (Vertical Crossline)
        fig.add_trace(
            go.Surface(
                x=np.full_like(Y_x, x[mid_x]),
                y=Y_x,
                z=Z_x,
                surfacecolor=val[:, mid_x, :],
                colorscale=cmaps[prop],
                name="Fatia X",
                legendgroup=prop,
                cmin=vmin,
                cmax=vmax,
                visible=ativo,
                showscale=False,
                **hover_x,
            )
        )

        # 3. Fatia Y (Vertical Inline)
        fig.add_trace(
            go.Surface(
                x=X_y,
                y=np.full_like(X_y, y[mid_y]),
                z=Z_y,
                surfacecolor=val[mid_y, :, :],
                colorscale=cmaps[prop],
                name="Fatia Y",
                legendgroup=prop,
                cmin=vmin,
                cmax=vmax,
                visible=ativo,
                showscale=False,
                **hover_y,
            )
        )

        # 4. Volume 3D Completo (Ativável na legenda)
        val_sub = val[::2, ::2, :]
        fig.add_trace(
            go.Volume(
                x=X_vol.flatten(),
                y=Y_vol.flatten(),
                z=Z_vol.flatten(),
                value=val_sub.flatten(),
                isomin=vmin,
                isomax=vmax,
                opacity=0.10,
                surface_count=15,
                colorscale=cmaps[prop],
                name="Volume 3D",
                legendgroup=prop,
                visible=("legendonly" if ativo else False),
                showscale=False,
                **hover_volume,
            )
        )

    fig.update_layout(
        height=760,
        title=dict(
            text="Modelo Turbidítico 3D — Fatias Ortogonais Interativas",
            font=dict(size=20),
            x=0.02,
            y=0.985,
            xanchor="left",
            yanchor="top",
        ),
        legend=dict(
            orientation="h",
            x=0.02,
            y=0.99,
            xanchor="left",
            yanchor="middle",
            font=dict(size=12),
        ),
        scene=dict(
            domain=dict(x=[0.02, 0.83], y=[0.02, 0.98]),
            xaxis_title="X (m)",
            yaxis_title="Y (m)",
            zaxis_title="Profundidade Z (m)",
            zaxis=dict(autorange="reversed"),  # Geologia: profundidade aumenta para baixo
            aspectratio=dict(x=1.2, y=1.0, z=0.5),
        ),
        margin=dict(l=30, r=30, b=30, t=50),
    )

    # Plotly via CDN para carregamento rápido no GitHub Pages
    plot_div = fig.to_html(include_plotlyjs="cdn", full_html=False, div_id="turbidite-plot")
    property_metadata_json = json.dumps(browser_properties, separators=(",", ":"))
    compressed_fields_json = json.dumps(compressed_fields, separators=(",", ":"))
    axes_json = json.dumps({"x": x.tolist(), "y": y.tolist(), "z": z.tolist()})
    y_indices_json = json.dumps(idx_y_list)
    x_indices_json = json.dumps(idx_x_list)
    options_html = "".join(
        f'<option value="{prop}">{property_specs[prop]["label"]}</option>'
        for prop in propriedades
    )

    template_html = """<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Modelo Turbidítico 3D - Visualização Interativa</title>
  <style>
        * {
      box-sizing: border-box;
        }
        html, body {
      margin: 0;
      padding: 0;
      background-color: #edf2f7;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }
        .page-wrapper {
      padding: 25px 35px 50px 35px;
      min-height: 100vh;
        }
        .card-container {
      max-width: 1550px;
      margin: 0 auto;
      background-color: #ffffff;
      border-radius: 14px;
      box-shadow: 0 6px 24px rgba(0, 0, 0, 0.08);
      padding: 20px 20px 30px 20px;
      overflow: visible;
        }
        .controls {
            display: grid;
            grid-template-columns: minmax(220px, 1.2fr) repeat(3, minmax(150px, 1fr));
            align-items: end;
            gap: 16px;
            margin: 0 8px 12px;
        }
        .control {
            display: grid;
            gap: 6px;
            color: #344054;
            font-size: 13px;
            font-weight: 600;
        }
        .control select {
            width: 100%;
            min-height: 38px;
            padding: 0 10px;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            background: #fff;
            color: #1f2937;
            font: inherit;
        }
        .range-heading {
            display: flex;
            justify-content: space-between;
            gap: 8px;
            white-space: nowrap;
        }
        .control input[type="range"] {
            width: 100%;
            margin: 6px 0 4px;
            accent-color: #1976a3;
        }
        @media (max-width: 760px) {
            .page-wrapper { padding: 12px; }
            .card-container { padding: 12px; }
            .controls { grid-template-columns: 1fr 1fr; gap: 12px; }
        }
  </style>
</head>
<body>
  <div class="page-wrapper">
    <div class="card-container">
            <div class="controls">
                <label class="control" for="property-select">Propriedade
                    <select id="property-select">__PROPERTY_OPTIONS__</select>
                </label>
                <label class="control" for="slider-z">
                    <span class="range-heading"><span>Fatia Z</span><output id="value-z"></output></span>
                    <input id="slider-z" type="range" min="0" max="__Z_MAX__" value="__MID_Z__">
                </label>
                <label class="control" for="slider-y">
                    <span class="range-heading"><span>Fatia Y</span><output id="value-y"></output></span>
                    <input id="slider-y" type="range" min="0" max="__Y_MAX__" value="__MID_Y__">
                </label>
                <label class="control" for="slider-x">
                    <span class="range-heading"><span>Fatia X</span><output id="value-x"></output></span>
                    <input id="slider-x" type="range" min="0" max="__X_MAX__" value="__MID_X__">
                </label>
            </div>
            __PLOT_DIV__
    </div>
  </div>
    <script>
        const propertyMetadata = __PROPERTY_METADATA__;
        const compressedFields = __COMPRESSED_FIELDS__;
        const axes = __AXES__;
        const yIndices = __Y_INDICES__;
        const xIndices = __X_INDICES__;
        const propertySelect = document.getElementById("property-select");
        const sliderZ = document.getElementById("slider-z");
        const sliderY = document.getElementById("slider-y");
        const sliderX = document.getElementById("slider-x");
        const plot = document.getElementById("turbidite-plot");
        const ny = axes.y.length;
        const nx = axes.x.length;
        const nz = axes.z.length;
        let activeData = null;
        let activeProperty = null;

        async function decodeField(name) {
            const binary = atob(compressedFields[name]);
            const compressed = Uint8Array.from(binary, character => character.charCodeAt(0));
            const stream = new Blob([compressed]).stream().pipeThrough(new DecompressionStream("deflate"));
            const buffer = await new Response(stream).arrayBuffer();
            return new Float32Array(buffer);
        }

        function getValue(data, iy, ix, iz) {
            return data[(iy * nx + ix) * nz + iz];
        }

        function categoryLabel(meta, value) {
            const code = Math.round(value);
            const index = code - meta.categoryOffset;
            return meta.categoryNames && index >= 0 && index < meta.categoryNames.length
                ? meta.categoryNames[index]
                : String(code);
        }

        function labelsFor(meta, values) {
            if (!meta.categorical) return values;
            return values.map(row => row.map(value => categoryLabel(meta, value)));
        }

        function makeSlices(data) {
            const iz = Number(sliderZ.value);
            const iy = yIndices[Number(sliderY.value)];
            const ix = xIndices[Number(sliderX.value)];
            const zSlice = Array.from({ length: ny }, (_, row) =>
                Array.from({ length: nx }, (_, column) => getValue(data, row, column, iz)));
            const xSlice = Array.from({ length: ny }, (_, row) =>
                Array.from({ length: nz }, (_, layer) => getValue(data, row, ix, layer)));
            const ySlice = Array.from({ length: nx }, (_, column) =>
                Array.from({ length: nz }, (_, layer) => getValue(data, iy, column, layer)));
            return { iz, iy, ix, zSlice, xSlice, ySlice };
        }

        function updateReadouts(indices) {
            document.getElementById("value-z").textContent = `${axes.z[indices.iz]} m`;
            document.getElementById("value-y").textContent = `${axes.y[indices.iy]} m`;
            document.getElementById("value-x").textContent = `${axes.x[indices.ix]} m`;
        }

        function updatePlot() {
            if (!activeData || !activeProperty) return;
            const meta = propertyMetadata[activeProperty];
            const { iz, iy, ix, zSlice, xSlice, ySlice } = makeSlices(activeData);
            const zGrid = Array.from({ length: ny }, () => Array(nx).fill(axes.z[iz]));
            const xGrid = Array.from({ length: ny }, () => Array(nz).fill(axes.x[ix]));
            const yGrid = Array.from({ length: nx }, () => Array(nz).fill(axes.y[iy]));
            const customZ = labelsFor(meta, zSlice);
            const customX = labelsFor(meta, xSlice);
            const customY = labelsFor(meta, ySlice);
            const hoverTemplate = `x: %{x}<br>y: %{y}<br>z: %{z}<br>${meta.label}: %{customdata}<extra></extra>`;
            const colorscale = meta.colorscale;

            Plotly.restyle(plot, {
                surfacecolor: [zSlice, xSlice, ySlice],
                colorscale,
                cmin: meta.minimum,
                cmax: meta.maximum,
                customdata: [customZ, customX, customY],
                hovertemplate: hoverTemplate,
            }, [0, 1, 2]);
            Plotly.restyle(plot, { z: [zGrid] }, [0]);
            Plotly.restyle(plot, { x: [xGrid] }, [1]);
            Plotly.restyle(plot, { y: [yGrid] }, [2]);

            const volumeValues = [];
            for (let row = 0; row < ny; row += 2) {
                for (let column = 0; column < nx; column += 2) {
                    for (let layer = 0; layer < nz; layer += 1) {
                        volumeValues.push(getValue(activeData, row, column, layer));
                    }
                }
            }
            const volumeCustomdata = meta.categorical
                ? volumeValues.map(value => categoryLabel(meta, value))
                : volumeValues;
            Plotly.restyle(plot, {
                value: [volumeValues],
                isomin: meta.minimum,
                isomax: meta.maximum,
                colorscale,
                customdata: [volumeCustomdata],
                hovertemplate: hoverTemplate,
            }, [3]);
            Plotly.restyle(plot, {
                colorbar: [{
                    title: meta.label,
                    x: 0.86,
                    y: 0.58,
                    len: 0.52,
                    tickmode: meta.categorical ? "array" : "auto",
                    tickvals: meta.categorical ? meta.tickvals : null,
                    ticktext: meta.categorical ? meta.ticktext : null,
                }],
            }, [0]);
            updateReadouts({ iz, iy, ix });
        }

        async function selectProperty() {
            const requestedProperty = propertySelect.value;
            activeProperty = requestedProperty;
            activeData = await decodeField(requestedProperty);
            if (propertySelect.value === requestedProperty) updatePlot();
        }

        propertySelect.addEventListener("change", () => selectProperty().catch(console.error));
        sliderZ.addEventListener("input", updatePlot);
        sliderY.addEventListener("input", updatePlot);
        sliderX.addEventListener("input", updatePlot);

        function initializePlot() {
            if (!plot.data || !window.Plotly) {
                requestAnimationFrame(initializePlot);
                return;
            }
            selectProperty().catch(console.error);
        }
        initializePlot();
    </script>
</body>
</html>
"""
    template_html = (
        template_html.replace("__PROPERTY_OPTIONS__", options_html)
        .replace("__PLOT_DIV__", plot_div)
        .replace("__PROPERTY_METADATA__", property_metadata_json)
        .replace("__COMPRESSED_FIELDS__", compressed_fields_json)
        .replace("__AXES__", axes_json)
        .replace("__Y_INDICES__", y_indices_json)
        .replace("__X_INDICES__", x_indices_json)
        .replace("__Z_MAX__", str(len(z) - 1))
        .replace("__Y_MAX__", str(len(idx_y_list) - 1))
        .replace("__X_MAX__", str(len(idx_x_list) - 1))
        .replace("__MID_Z__", str(mid_z))
        .replace("__MID_Y__", str(active_y))
        .replace("__MID_X__", str(active_x))
    )

    destino = (base_dir / arquivo_saida).resolve()
    with open(destino, "w", encoding="utf-8") as f:
        f.write(template_html)

    # Gera também visualizacao_3d_interativa.html para compatibilidade
    copia_legado = (base_dir / "visualizacao_3d_interativa.html").resolve()
    if destino != copia_legado:
        with open(copia_legado, "w", encoding="utf-8") as f:
            f.write(template_html)

    print(f"Arquivo HTML gerado com sucesso: {destino}")

    if abrir_navegador:
        print("Abrindo navegador padrão...")
        webbrowser.open(destino.as_uri())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera a visualização 3D do modelo turbidítico.")
    parser.add_argument(
        "arquivo_npz",
        nargs="?",
        help="Arquivo NPZ de entrada (padrão: modelo_reservatorio_3d.npz)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Gera o HTML sem abrir o navegador.",
    )
    argumentos = parser.parse_args()
    gerar_visualizacao_3d(
        caminho_npz=argumentos.arquivo_npz,
        abrir_navegador=not argumentos.no_browser,
    )

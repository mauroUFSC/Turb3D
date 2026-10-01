import ast
import base64
import argparse
import json
import sys
import webbrowser
import zlib
from pathlib import Path
import numpy as np
import plotly.graph_objects as go


def resolver_caminho_base() -> Path:
    """Retorna o diretório base da aplicação (suporta modo congelado PyInstaller)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).parent.resolve()


# Especificações de propriedades conhecidas para modelos geológicos e de reservatório
PROPERTY_SPECS_BASE = {
    "porosity": {
        "keys": ("phi", "porosity", "poro", "porosidade"),
        "label": "Porosidade (phi)",
        "colorscale": "Viridis",
        "decimals": 4,
    },
    "permeability": {
        "keys": ("K", "permeability_mD", "permeability", "perm", "permeabilidade"),
        "label": "Permeabilidade (K)",
        "colorscale": "Turbo",
        "decimals": 2,
    },
    "vertical_permeability": {
        "keys": ("Kz", "kz", "perm_z", "permeabilidade_vertical"),
        "label": "Permeabilidade vertical (Kz)",
        "colorscale": "Turbo",
        "decimals": 2,
    },
    "shale_volume": {
        "keys": ("Vsh", "vsh", "volume_folhelho", "shale_fraction"),
        "label": "Volume de folhelho (Vsh)",
        "colorscale": "Viridis",
        "decimals": 3,
    },
    "vp": {
        "keys": ("Vp", "vp_ms", "vp", "velocidade_p"),
        "label": "Velocidade P (Vp)",
        "colorscale": "Turbo",
        "decimals": 2,
    },
    "vs": {
        "keys": ("Vs", "vs_ms", "vs", "velocidade_s"),
        "label": "Velocidade S (Vs)",
        "colorscale": "Turbo",
        "decimals": 2,
    },
    "density": {
        "keys": ("rho", "density_gcc", "density", "densidade"),
        "label": "Densidade (rho)",
        "colorscale": "Viridis",
        "decimals": 3,
    },
    "gamma_ray": {
        "keys": ("GR", "gr", "raios_gama"),
        "label": "Raios gama (GR)",
        "colorscale": "Viridis",
        "decimals": 2,
    },
    "resistivity": {
        "keys": ("resistivity", "res", "resistividade"),
        "label": "Resistividade",
        "colorscale": "Turbo",
        "decimals": 2,
    },
    "water_saturation": {
        "keys": ("Sw", "water_saturation", "sw", "saturacao_agua"),
        "label": "Saturação de água (Sw)",
        "colorscale": "Viridis",
        "decimals": 3,
    },
    "acoustic_impedance": {
        "keys": ("Ip", "acoustic_impedance", "ip", "impedancia_acustica"),
        "label": "Impedância P (Ip)",
        "colorscale": "Turbo",
        "decimals": 2,
    },
    "shear_impedance": {
        "keys": ("Is", "is", "impedancia_cisalhante"),
        "label": "Impedância S (Is)",
        "colorscale": "Turbo",
        "decimals": 2,
    },
    "normalized_acoustic_impedance": {
        "keys": ("Ip_norm", "ip_norm"),
        "label": "Impedância P normalizada",
        "colorscale": "RdBu",
        "decimals": 3,
    },
    "normalized_shear_impedance": {
        "keys": ("Is_norm", "is_norm"),
        "label": "Impedância S normalizada",
        "colorscale": "RdBu",
        "decimals": 3,
    },
    "facies": {
        "keys": ("facies", "facio", "facies_code"),
        "label": "Fácies",
        "colorscale": "Portland",
        "decimals": 0,
        "categorical": True,
    },
    "unit": {
        "keys": ("unit", "unidade", "zone"),
        "label": "Unidade",
        "colorscale": "Viridis",
        "decimals": 0,
        "categorical": True,
    },
    "architecture": {
        "keys": ("architecture", "arquitetura", "arch"),
        "label": "Arquitetura",
        "colorscale": "Portland",
        "decimals": 0,
        "categorical": True,
    },
}


def _extrair_metadados(dados) -> dict:
    """Extrai informações adicionais e metadados salvos no arquivo .npz."""
    if "metadata" not in dados:
        return {}
    meta_val = dados["metadata"]
    try:
        if isinstance(meta_val, np.ndarray) and meta_val.ndim == 0:
            meta_val = meta_val.item()
        if isinstance(meta_val, str):
            try:
                return json.loads(meta_val)
            except Exception:
                return ast.literal_eval(meta_val)
        elif isinstance(meta_val, dict):
            return meta_val
    except Exception:
        pass
    return {}


def _obter_nomes_categorias(dados, metadados=None) -> dict:
    """Identifica nomes de categorias para fácies, arquitetura e outras variáveis discretas."""
    category_names = {}
    if "facies_names" in dados:
        category_names["facies"] = np.asarray(dados["facies_names"]).astype(str)
    if "architecture_names" in dados:
        category_names["architecture"] = np.asarray(dados["architecture_names"]).astype(str)

    # Verifica se há dicionários de categorias nos metadados
    if metadados and isinstance(metadados, dict):
        if "facies" in metadados and isinstance(metadados["facies"], dict) and "facies" not in category_names:
            facies_dict = metadados["facies"]
            # Converte chaves inteiras ordenadas em lista de strings
            sorted_keys = sorted([int(k) for k in facies_dict.keys()])
            category_names["facies"] = np.array([facies_dict[k] for k in sorted_keys], dtype=str)

    # Busca genérica para outras propriedades <prop>_names
    for k in dados.files:
        if k.endswith("_names") and k[:-6] not in category_names:
            category_names[k[:-6]] = np.asarray(dados[k]).astype(str)

    return category_names


def inspecionar_modelo_npz(caminho_npz: str | Path) -> dict:
    """
    Inspeciona genericamente um arquivo .npz e extrai dimensões, coordenadas
    e propriedades tridimensionais sem travar a interface.
    """
    caminho = Path(caminho_npz).resolve()
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    dados = np.load(str(caminho), allow_pickle=True)
    chaves = list(dados.keys())

    # Detectar arrays 3D
    arrays_3d_info = {}
    for k in chaves:
        arr = dados[k]
        if hasattr(arr, "ndim") and arr.ndim == 3:
            arrays_3d_info[k] = arr

    if not arrays_3d_info:
        raise ValueError(
            f"O arquivo '{caminho.name}' não contém arrays tridimensionais (3D). "
            f"Chaves disponíveis: {chaves}"
        )

    # Identificar coordenadas
    primeiro_nome = next(iter(arrays_3d_info.keys()))
    shape_ref = arrays_3d_info[primeiro_nome].shape

    def buscar_vetor(candidatos, default_len, default_step):
        for c in candidatos:
            for k in chaves:
                if k.lower() == c.lower():
                    v = np.asarray(dados[k])
                    if v.ndim == 1 and len(v) == default_len:
                        return v.astype(float)
                    elif v.ndim > 1:
                        u = np.unique(v)
                        if len(u) == default_len:
                            return np.sort(u).astype(float)
        return np.arange(default_len, dtype=float) * default_step

    # Se shape_ref for (s0, s1, s2)
    # Tenta associar x, y, z
    chave_x = next((k for k in ("x_m", "x", "X_m", "X", "coord_x", "easting") if k in chaves), None)
    chave_y = next((k for k in ("y_m", "y", "Y_m", "Y", "coord_y", "northing") if k in chaves), None)
    chave_z = next((k for k in ("z_m", "z", "Z_m", "Z", "coord_z", "depth", "profundidade", "tvd") if k in chaves), None)

    len_x = len(np.asarray(dados[chave_x]).flatten()) if chave_x else None
    len_y = len(np.asarray(dados[chave_y]).flatten()) if chave_y else None
    len_z = len(np.asarray(dados[chave_z]).flatten()) if chave_z else None

    if len_x and len_y and len_z:
        nx, ny, nz = len_x, len_y, len_z
    else:
        # Se shape_ref = (s0, s1, s2) onde s0 é Z (menor)
        if shape_ref[0] <= min(shape_ref[1], shape_ref[2]):
            nz, ny, nx = shape_ref[0], shape_ref[1], shape_ref[2]
        else:
            ny, nx, nz = shape_ref[0], shape_ref[1], shape_ref[2]

    x = buscar_vetor(["x_m", "x", "X_m", "X", "coord_x", "easting"], nx, 25.0)
    y = buscar_vetor(["y_m", "y", "Y_m", "Y", "coord_y", "northing"], ny, 25.0)
    z = buscar_vetor(["z_m", "z", "Z_m", "Z", "coord_z", "depth", "profundidade", "tvd"], nz, 2.5)

    metadados = _extrair_metadados(dados)
    category_names = _obter_nomes_categorias(dados, metadados)

    # Identificar propriedades e rótulos
    propriedades_detectadas = []
    matched_keys = set()

    for prop_id, spec in PROPERTY_SPECS_BASE.items():
        for k in spec["keys"]:
            if k in arrays_3d_info:
                arr = arrays_3d_info[k]
                matched_keys.add(k)
                is_cat = spec.get("categorical", False)
                propriedades_detectadas.append({
                    "id": prop_id,
                    "chave_orig": k,
                    "label": spec["label"],
                    "shape": list(arr.shape),
                    "dtype": str(arr.dtype),
                    "min": float(np.nanmin(arr)),
                    "max": float(np.nanmax(arr)),
                    "categorical": is_cat,
                    "category_names": category_names.get(prop_id, []).tolist() if prop_id in category_names else [],
                })
                break

    # Adicionar arrays 3D genéricos não mapeados
    for k, arr in arrays_3d_info.items():
        if k not in matched_keys:
            is_int = np.issubdtype(arr.dtype, np.integer)
            sample = arr[::max(1, arr.shape[0] // 5), ::max(1, arr.shape[1] // 5), ::max(1, arr.shape[2] // 5)]
            unique_vals = np.unique(sample) if sample.size > 0 else []
            is_cat = bool(is_int and len(unique_vals) <= 30)
            propriedades_detectadas.append({
                "id": k,
                "chave_orig": k,
                "label": k.replace("_", " ").title(),
                "shape": list(arr.shape),
                "dtype": str(arr.dtype),
                "min": float(np.nanmin(arr)),
                "max": float(np.nanmax(arr)),
                "categorical": is_cat,
                "category_names": [],
            })

    tamanho_bytes = caminho.stat().st_size
    tamanho_mb = round(tamanho_bytes / (1024 * 1024), 2)

    return {
        "caminho": str(caminho),
        "nome_arquivo": caminho.name,
        "tamanho_mb": tamanho_mb,
        "nx": int(nx),
        "ny": int(ny),
        "nz": int(nz),
        "total_celulas": int(nx * ny * nz),
        "x_min": float(np.min(x)),
        "x_max": float(np.max(x)),
        "y_min": float(np.min(y)),
        "y_max": float(np.max(y)),
        "z_min": float(np.min(z)),
        "z_max": float(np.max(z)),
        "dx": float(x[1] - x[0]) if len(x) > 1 else 1.0,
        "dy": float(y[1] - y[0]) if len(y) > 1 else 1.0,
        "dz": float(z[1] - z[0]) if len(z) > 1 else 1.0,
        "propriedades": propriedades_detectadas,
        "metadados": metadados,
    }


def gerar_visualizacao_3d(
    caminho_npz: str | Path = None,
    arquivo_saida: str | Path = "index.html",
    abrir_navegador: bool = True,
    salvar_copia_index: bool = True,
    callback_progresso=None,
    callback_log=None,
) -> Path:
    """
    Carrega o modelo .npz (de forma genérica), processa os volumes e fatias ortogonais
    e gera a visualização HTML 3D interativa standalone com Plotly.
    """
    def log(msg: str):
        if callback_log:
            callback_log(msg)
        else:
            print(msg)

    def progresso(percent: int, status: str):
        if callback_progresso:
            callback_progresso(percent, status)
        log(f"[{percent}%] {status}")

    base_dir = resolver_caminho_base()
    if caminho_npz is None:
        caminho_npz = base_dir / "modelo_reservatorio_3d.npz"
    else:
        caminho_npz = Path(caminho_npz).resolve()

    if not caminho_npz.is_file():
        raise FileNotFoundError(f"Arquivo de dados .npz não encontrado: {caminho_npz}")

    progresso(10, f"Carregando arquivo {caminho_npz.name}...")
    dados = np.load(str(caminho_npz), allow_pickle=True)
    chaves = list(dados.keys())

    # Detectar arrays 3D
    arrays_3d = {}
    for k in chaves:
        arr = dados[k]
        if hasattr(arr, "ndim") and arr.ndim == 3:
            arrays_3d[k] = arr

    if not arrays_3d:
        raise ValueError(f"O arquivo .npz '{caminho_npz.name}' não possui arrays 3D.")

    primeiro_arr = next(iter(arrays_3d.values()))
    shape_ref = primeiro_arr.shape

    # Detectar vetores de coordenadas
    chave_x = next((k for k in ("x_m", "x", "X_m", "X", "coord_x", "easting") if k in chaves), None)
    chave_y = next((k for k in ("y_m", "y", "Y_m", "Y", "coord_y", "northing") if k in chaves), None)
    chave_z = next((k for k in ("z_m", "z", "Z_m", "Z", "coord_z", "depth", "profundidade", "tvd") if k in chaves), None)

    len_x = len(np.asarray(dados[chave_x]).flatten()) if chave_x else None
    len_y = len(np.asarray(dados[chave_y]).flatten()) if chave_y else None
    len_z = len(np.asarray(dados[chave_z]).flatten()) if chave_z else None

    if len_x and len_y and len_z:
        nx, ny, nz = len_x, len_y, len_z
    else:
        if shape_ref[0] <= min(shape_ref[1], shape_ref[2]):
            nz, ny, nx = shape_ref[0], shape_ref[1], shape_ref[2]
        else:
            ny, nx, nz = shape_ref[0], shape_ref[1], shape_ref[2]

    def buscar_coord(chave, default_len, default_step):
        if chave is not None:
            v = np.asarray(dados[chave])
            if v.ndim == 1 and len(v) == default_len:
                return v.astype(float)
            elif v.ndim > 1:
                u = np.unique(v)
                if len(u) == default_len:
                    return np.sort(u).astype(float)
        return np.arange(default_len, dtype=float) * default_step

    x = buscar_coord(chave_x, nx, 25.0)
    y = buscar_coord(chave_y, ny, 25.0)
    z = buscar_coord(chave_z, nz, 2.5)

    progresso(25, f"Grade identificada: Nx={nx}, Ny={ny}, Nz={nz} ({nx*ny*nz:,} células)")

    metadados = _extrair_metadados(dados)
    category_names = _obter_nomes_categorias(dados, metadados)
    category_offsets = {"facies": 1, "architecture": 0}

    def labels_for_category(prop, values):
        codes = np.rint(values).astype(int)
        labels = codes.astype(str).astype(object)
        names = category_names.get(prop)
        if names is None:
            return labels
        offset = category_offsets.get(prop, 0)
        indices = codes - offset
        valid = (indices >= 0) & (indices < len(names))
        labels[valid] = names[indices[valid]]
        return labels

    # Construir especificações completas de propriedades
    property_specs = dict(PROPERTY_SPECS_BASE)
    propriedades = []
    matched_keys = set()

    for prop, spec in list(property_specs.items()):
        for k in spec["keys"]:
            if k in arrays_3d:
                matched_keys.add(k)
                propriedades.append(prop)
                break

    # Adicionar campos 3D adicionais genéricos
    for k, arr in arrays_3d.items():
        if k not in matched_keys:
            is_int = np.issubdtype(arr.dtype, np.integer)
            sample = arr[::max(1, arr.shape[0] // 5), ::max(1, arr.shape[1] // 5), ::max(1, arr.shape[2] // 5)]
            unique_vals = np.unique(sample) if sample.size > 0 else []
            is_categorical = bool(is_int and len(unique_vals) <= 30)
            diff = float(np.nanmax(sample) - np.nanmin(sample)) if len(sample) else 0.0
            decimals = 0 if is_categorical else (4 if diff < 1.0 else (2 if diff < 1000 else 1))
            label = k.replace("_", " ").title()
            colorscale = "Portland" if is_categorical else "Viridis"
            property_specs[k] = {
                "keys": (k,),
                "label": label,
                "colorscale": colorscale,
                "decimals": decimals,
                "categorical": is_categorical,
            }
            propriedades.append(k)

    cmaps = {prop: property_specs[prop]["colorscale"] for prop in propriedades}

    progresso(40, f"Processando e ajustando orientação de {len(propriedades)} propriedades...")

    # Função para ajustar orientação para target_shape = (ny, nx, nz)
    def orientar_array(val):
        s = val.shape
        if s == (ny, nx, nz):
            return val
        if s == (nz, ny, nx):
            return np.transpose(val, (1, 2, 0))
        if s == (nx, ny, nz):
            return np.transpose(val, (1, 0, 2))
        if s == (nz, nx, ny):
            return np.transpose(val, (2, 1, 0))
        if s == (ny, nz, nx):
            return np.transpose(val, (0, 2, 1))
        if s == (nx, nz, ny):
            return np.transpose(val, (2, 0, 1))
        return val

    data_dict = {}
    for p in propriedades:
        source_key = next(key for key in property_specs[p]["keys"] if key in arrays_3d)
        val = np.asarray(arrays_3d[source_key], dtype=np.float32)
        val = orientar_array(val)
        data_dict[p] = np.round(val, property_specs[p]["decimals"])

    # Malhas para fatias e volume
    X_z, Y_z = np.meshgrid(x, y)
    Y_x, Z_x = np.meshgrid(y, z, indexing="ij")
    X_y, Z_y = np.meshgrid(x, z, indexing="ij")

    # Amostragem otimizada para volume 3D
    vol_step = 2 if (len(x) >= 40 and len(y) >= 40) else 1
    x_sub = x[::vol_step]
    y_sub = y[::vol_step]
    Y_vol, X_vol, Z_vol = np.meshgrid(y_sub, x_sub, z, indexing="ij")

    mid_z = len(z) // 2
    mid_x = len(x) // 2
    mid_y = len(y) // 2

    progresso(60, "Comprimindo volumes para execução rápida no navegador...")

    browser_properties = {}
    compressed_fields = {}
    for prop in propriedades:
        val = data_dict[prop]
        is_cat = bool(property_specs[prop].get("categorical"))
        category_codes = np.unique(np.rint(val).astype(int)) if is_cat else []
        category_names_for_prop = category_names.get(prop)
        browser_properties[prop] = {
            "label": property_specs[prop]["label"],
            "minimum": float(np.nanmin(val)),
            "maximum": float(np.nanmax(val)),
            "colorscale": property_specs[prop]["colorscale"],
            "categorical": is_cat,
            "categoryNames": category_names_for_prop.tolist() if category_names_for_prop is not None else None,
            "categoryOffset": category_offsets.get(prop, 0),
            "tickvals": category_codes.tolist() if len(category_codes) else [],
            "ticktext": labels_for_category(prop, category_codes).tolist() if len(category_codes) else [],
        }
        values_bytes = np.ascontiguousarray(val, dtype="<f4").tobytes()
        compressed_fields[prop] = base64.b64encode(zlib.compress(values_bytes)).decode("ascii")

    slice_step = 2 if (len(y) > 40 and len(x) > 40) else 1
    idx_y_list = list(range(0, len(y), slice_step))
    if (len(y) - 1) not in idx_y_list:
        idx_y_list.append(len(y) - 1)
    idx_x_list = list(range(0, len(x), slice_step))
    if (len(x) - 1) not in idx_x_list:
        idx_x_list.append(len(x) - 1)

    active_y = idx_y_list.index(mid_y if mid_y in idx_y_list else idx_y_list[len(idx_y_list) // 2])
    active_x = idx_x_list.index(mid_x if mid_x in idx_x_list else idx_x_list[len(idx_x_list) // 2])

    progresso(75, "Construindo cena Plotly 3D...")

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
                "customdata": labels_for_category(prop, val[::vol_step, ::vol_step, :]).flatten(),
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

        # 4. Volume 3D Completo
        val_sub = val[::vol_step, ::vol_step, :]
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
            font=dict(size=18),
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
            zaxis=dict(autorange="reversed"),
            aspectratio=dict(x=1.2, y=1.0, z=0.5),
        ),
        margin=dict(l=30, r=30, b=30, t=50),
    )

    progresso(88, "Renderizando templates HTML e scripts interativos...")

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
        const volStep = __VOL_STEP__;
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
            for (let row = 0; row < ny; row += volStep) {
                for (let column = 0; column < nx; column += volStep) {
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
        .replace("__VOL_STEP__", str(vol_step))
        .replace("__Z_MAX__", str(len(z) - 1))
        .replace("__Y_MAX__", str(len(idx_y_list) - 1))
        .replace("__X_MAX__", str(len(idx_x_list) - 1))
        .replace("__MID_Z__", str(mid_z))
        .replace("__MID_Y__", str(active_y))
        .replace("__MID_X__", str(active_x))
    )

    progresso(95, "Salvando arquivo HTML gerado...")

    destino = Path(arquivo_saida)
    if not destino.is_absolute():
        ref_dir = caminho_npz.parent if caminho_npz.exists() else base_dir
        destino = (ref_dir / destino).resolve()

    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        f.write(template_html)

    # Gera também visualizacao_3d_interativa.html se solicitado ou se for o arquivo padrão
    if salvar_copia_index:
        copia_index = destino.parent / "index.html"
        if destino != copia_index:
            try:
                with open(copia_index, "w", encoding="utf-8") as f:
                    f.write(template_html)
            except Exception:
                pass

    log(f"Arquivo HTML gerado com sucesso: {destino}")
    progresso(100, "Visualização 3D concluída com sucesso!")

    if abrir_navegador:
        log("Abrindo navegador padrão...")
        webbrowser.open(destino.as_uri())

    return destino


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera a visualização 3D do modelo turbidítico.")
    parser.add_argument(
        "arquivo_npz",
        nargs="?",
        help="Arquivo NPZ de entrada (padrão: modelo_reservatorio_3d.npz)",
    )
    parser.add_argument(
        "-o", "--output",
        default="index.html",
        help="Caminho do arquivo HTML de saída (padrão: index.html)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Gera o HTML sem abrir o navegador.",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Abre a interface gráfica (GUI).",
    )
    argumentos = parser.parse_args()

    if argumentos.gui:
        from app_gui import iniciar_gui
        iniciar_gui(argumentos.arquivo_npz)
    else:
        gerar_visualizacao_3d(
            caminho_npz=argumentos.arquivo_npz,
            arquivo_saida=argumentos.output,
            abrir_navegador=not argumentos.no_browser,
        )

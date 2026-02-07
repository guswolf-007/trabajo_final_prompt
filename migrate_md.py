
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
from pathlib import Path

SRC_DIR = Path("rag")
DST_DIR = Path("rag_migrated")

# ---- Helpers ----

def normalize_spaces(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()

def strip_blockquotes(md: str) -> str:
    # Quita prefijo "> " de blockquotes (mantiene contenido)
    return re.sub(r"(?m)^\s*>\s?", "", md)

def fix_inline_dashes(md: str) -> str:
    # Convierte patrones "texto: - item" en:
    # texto:
    # - item
    md = re.sub(r":\s*-\s*", ":\n- ", md)
    # Convierte " - **" pegado en nueva línea bullet
    md = re.sub(r"\s+-\s+\*\*", "\n- **", md)
    return md

def clean_bullets(md: str) -> str:
    # Normaliza bullets tipo "* " a "- "
    md = re.sub(r"(?m)^\s*\*\s+", "- ", md)
    return md

def title_case_bank(name: str) -> str:
    # Mantiene "BCI" como BCI, etc. Si no, capitaliza suave.
    n = name.strip()
    if n.upper() in {"BCI", "BICE", "ITAU", "Itaú".upper()}:
        return n
    return n

def infer_bank_id(text: str, filename: str) -> str:
    # Intenta extraer desde "# Banco: X" o desde el nombre del archivo
    m = re.search(r"(?m)^\s*#\s*Banco\s*:\s*(.+)\s*$", text)
    if m:
        base = m.group(1).strip().lower()
    else:
        base = filename.lower()

    base = base.replace(".md", "")
    base = re.sub(r"^\d+[_\- ]*", "", base)
    base = base.replace("banco_", "").replace("banco ", "")
    base = base.replace("chile", "de_chile") if "chile" in base and "santander" not in base else base
    base = base.replace("__", "_")
    base = re.sub(r"[^a-z0-9_]+", "_", base).strip("_")
    if "banco_de_chile" in base or "de_chile" in base:
        return "banco_de_chile"
    if "santander" in base:
        return "santander"
    if "estado" in base:
        return "banco_estado"
    if "bci" in base:
        return "bci"
    if "itau" in base or "ita" in base:
        return "itau"
    if "scotia" in base:
        return "scotiabank"
    return base or "otro"

def infer_bank_name(text: str, filename: str) -> str:
    m = re.search(r"(?m)^\s*#\s*Banco\s*:\s*(.+)\s*$", text)
    if m:
        return title_case_bank(m.group(1).strip())
    # fallback desde filename
    base = re.sub(r"^\d+[_\- ]*", "", filename.replace(".md", ""))
    base = base.replace("_", " ").strip()
    return title_case_bank(base)

def split_sections(md: str):
    """
    Devuelve lista de (h2_title, section_text) en base a "## ".
    Lo que quede antes del primer ## va a "Intro".
    """
    parts = re.split(r"(?m)^\s*##\s+", md)
    if len(parts) == 1:
        return [("Contenido", md.strip())]

    intro = parts[0].strip()
    sections = []
    for chunk in parts[1:]:
        # chunk empieza con "Titulo\n..."
        lines = chunk.split("\n", 1)
        title = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        sections.append((title, body))
    if intro:
        sections.insert(0, ("Intro", intro))
    return sections

def normalize_key_value_bullets(section_body: str) -> list[str]:
    out = []

    for raw in section_body.splitlines():
        line = raw.strip()
        if not line:
            continue

        # headers internos
        if re.match(r"^\s*#{1,6}\s+", line):
            out.append(line)
            continue

        # Normaliza bullets
        if line.startswith("* "):
            line = "- " + line[2:]
        if not line.startswith("- "):
            # si es texto normal lo dejamos igual
            out.append(line)
            continue

        # Quita exceso de asteriscos en TODA la línea
        line = re.sub(r"\*{3,}", "**", line)

        # Caso 1: "- **key:** value" o variantes con espacios raros
        m = re.match(r"^- \*\*(.+?)\*\*\s*:\s*(.+)$", line)
        if m:
            key = m.group(1)
            val = m.group(2)

            # Limpieza fuerte: elimina ** dentro de key y val, y espacios raros
            key = key.replace("**", "").strip().rstrip(":")
            val = val.replace("**", "").strip()

            out.append(f"- **{key}:** {val}")
            continue

        # Caso 2: "- key: value"
        m = re.match(r"^- ([^:]{1,80})\s*:\s*(.+)$", line)
        if m:
            key = m.group(1).replace("**", "").strip().rstrip(":")
            val = m.group(2).replace("**", "").strip()
            out.append(f"- **{key}:** {val}")
            continue

        # Caso 3: bullet normal sin key/value
        out.append(line)

    return out

def extract_summary(md: str) -> str | None:
    m = re.search(r"(?ms)^\s*##\s*Texto resumen para embeddings\s*\n(.+?)\s*$", md)
    if m:
        return normalize_spaces(m.group(1))
    return None

def squash_stars(md: str) -> str:
    # Reduce cualquier secuencia de *** o más a solo **
    md = re.sub(r"\*{3,}", "**", md)

    # Arregla patrones comunes tipo "**key:** ** value" -> "**key:** value"
    md = re.sub(r"(\*\*[^*]+\:\*\*)\s*\*\*\s*", r"\1 ", md)

    # Arregla bullets que quedaron como "- ****key" -> "- **key"
    md = re.sub(r"(?m)^(\s*-\s*)\*\*\*\*(.+)$", r"\1**\2", md)

    return md

def rebuild_markdown(original_md: str, filename: str) -> str:
    md = original_md
    md = strip_blockquotes(md)
    md = fix_inline_dashes(md)
    md = clean_bullets(md)
    md = squash_stars(md)

    bank_name = infer_bank_name(md, filename)
    bank_id = infer_bank_id(md, filename)
    summary = extract_summary(md)

    # elimina el header viejo "# Banco: X" si existe
    md = re.sub(r"(?m)^\s*#\s*Banco\s*:\s*.+\s*$", "", md).strip()

    sections = split_sections(md)

    # Armamos salida
    out = []
    out.append(f"# {bank_name}")
    out.append("")
    out.append("## Identificación")
    out.append(f"- **Banco:** {bank_name}")
    out.append(f"- **Banco ID:** {bank_id}")
    out.append("")

    # Mapeo suave de nombres de secciones a algo uniforme
    rename = {
        "Identificación": "Identificación",
        "Requisitos": "Requisitos",
        "Tamaño y cobertura": "Tamaño y cobertura",
        "Costos": "Costos de mantención",
        "Costos de mantención": "Costos de mantención",
        "Beneficios (tarjeta de crédito/cuenta corriente)": "Beneficios",
        "Experiencia y atención (1–5)": "Experiencia y atención (escala 1–5)",
        "Experiencia y atención (1-5)": "Experiencia y atención (escala 1–5)",
        "Tags de recuperación (derivados)": "Tags",
        "Texto resumen para embeddings": "Resumen para embeddings",
    }

    # Reagrupar: beneficios los partimos por subtemas si detectamos "Disponibilidad" / "incluidos"
    for title, body in sections:
        title = title.strip()
        if title == "Intro":
            continue
        if not body.strip():
            continue

        new_title = rename.get(title, title)
        # Ya reconstruimos Identificación al inicio
        if new_title == "Identificación":
            continue

        # Saltar el resumen original: lo repondremos al final
        if "Texto resumen para embeddings" in title or new_title == "Resumen para embeddings":
            continue

        # Beneficios: intentamos separar por bloques si hay claves tipo descuentos_...
        if new_title == "Beneficios":
            # dividimos por bullets "- **xxx:**"
            lines = body.splitlines()
            blocks = []
            current = []
            current_key = None

            for ln in lines:
                ln = ln.rstrip()
                m = re.match(r"^\s*-\s*\*\*(.+?)\*\*\s*:\s*(.+)\s*$", ln)
                if m:
                    # nuevo bloque
                    if current:
                        blocks.append((current_key, current))
                    current_key = m.group(1).strip().replace("_", " ")
                    current = [ln]
                else:
                    if ln.strip():
                        current.append(ln)
            if current:
                blocks.append((current_key, current))

            # si no pudimos dividir, dejamos como una sección
            if len(blocks) <= 1:
                out.append(f"## {new_title}")
                out.extend(normalize_key_value_bullets(body))
                out.append("")
            else:
                # render por sub-secciones
                for key, blk_lines in blocks:
                    if not key:
                        key = "Beneficios"
                    # heurística para títulos
                    pretty = key
                    if "descuentos" in pretty.lower() and "restaurant" in pretty.lower():
                        pretty = "Beneficios – Restaurantes"
                    elif "cuotas" in pretty.lower():
                        pretty = "Beneficios – Cuotas precio contado"
                    elif "retail" in pretty.lower():
                        pretty = "Beneficios – Retail"
                    elif "aeroline" in pretty.lower() or "aerolí" in pretty.lower():
                        pretty = "Beneficios – Aerolíneas"
                    elif "programa" in pretty.lower() or "puntos" in pretty.lower():
                        pretty = "Programa de puntos"
                    else:
                        pretty = f"Beneficios – {pretty}"

                    out.append(f"## {pretty}")
                    out.extend(normalize_key_value_bullets("\n".join(blk_lines)))
                    out.append("")
        else:
            out.append(f"## {new_title}")
            out.extend(normalize_key_value_bullets(body))
            out.append("")

    # Resumen al final
    out.append("## Resumen para embeddings")
    if summary:
        out.append(summary)
    else:
        # fallback: mini resumen a partir de costos/beneficios si existe, sino texto genérico
        out.append(f"{bank_name} (ID: {bank_id}). Este documento contiene requisitos, costos, beneficios y experiencia/atención.")
    out.append("")

    return "\n".join(out).strip() + "\n"

def main():
    if not SRC_DIR.exists():
        print(f"❌ No existe la carpeta: {SRC_DIR.resolve()}")
        return

    DST_DIR.mkdir(parents=True, exist_ok=True)

    md_files = sorted([p for p in SRC_DIR.iterdir() if p.suffix.lower() == ".md"])
    if not md_files:
        print("⚠️ No encontré archivos .md en rag/")
        return

    print(f"📂 Migrando {len(md_files)} archivos desde {SRC_DIR}/ -> {DST_DIR}/")

    for p in md_files:
        text = p.read_text(encoding="utf-8")
        migrated = rebuild_markdown(text, p.name)
        out_path = DST_DIR / p.name
        out_path.write_text(migrated, encoding="utf-8")
        print(f"✅ {p.name} -> {out_path}")

    print("\n🎉 Listo. Revisa 1–2 archivos en rag_migrated/ y luego reindexa tu RAG con esa carpeta.")

if __name__ == "__main__":
    main()


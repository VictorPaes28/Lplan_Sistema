from pathlib import Path

p = Path("suprimentos/templates/suprimentos/mapa_controle.html")
t = p.read_text(encoding="utf-8")

old_row = "&quick={{ selected.quick_find|urlencode }}\">{{ row.row_label }}</a>"
new_row = "&quick={{ selected.quick_find|urlencode }}&{{ matrix_stable_qs }}\">{{ row.row_label }}</a>"
if old_row in t:
    t = t.replace(old_row, new_row)
    print("row-links patched:", t.count(new_row))
else:
    print("row-link pattern missing; row-link count:", t.count("row-link"))

for mode, label in (
    ("bloco", "Por bloco"),
    ("pavimento", "Por pavimento"),
    ("apto", "Por unidade"),
):
    old = f'matrix_mode={mode}">{label}</a>'
    new = f'matrix_mode={mode}&{{{{ matrix_stable_qs }}}}">{label}</a>'
    if old in t:
        t = t.replace(old, new)
        print("matrix_mode", mode, "ok")
    else:
        print("matrix_mode", mode, "missing")

needle = '<input type="hidden" name="obra" value="{{ obra_selecionada.id|default:\'\' }}">'
insert = (
    needle
    + "\n                {% if ambiente_id %}"
    + '\n                <input type="hidden" name="ambiente_id" value="{{ ambiente_id }}">'
    + "\n                {% endif %}"
)
if 'name="ambiente_id"' not in t.split("mapaControleFilterForm", 1)[1][:900]:
    if needle in t:
        t = t.replace(needle, insert, 1)
        print("ambiente_id hidden ok")

old_layer = "&quick={{ selected.quick_find|urlencode }}\">"
new_layer = "&quick={{ selected.quick_find|urlencode }}&{{ matrix_stable_qs }}\">"
if old_layer in t:
    count = t.count(old_layer)
    t = t.replace(old_layer, new_layer)
    print("layer-cards patched:", count)

p.write_text(t, encoding="utf-8")
print("lines", len(t.splitlines()))

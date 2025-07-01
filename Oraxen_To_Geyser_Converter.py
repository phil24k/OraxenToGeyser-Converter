#!/usr/bin/env python3
"""
Bedrock & Oraxen Pack Generator v2.8

• Création manuelle items / blocks / armors (+ extras, aperçu 3D)
• Import dossier Oraxen (filtrage, extension .png auto)
• Génération des dossiers :
      bedrock_pack/
          ├─ manifest.json
          ├─ textures/item_texture.json
          ├─ textures/items/*.png
          ├─ textures/models/armor/*.png
          └─ attachables/<id>/<piece>.json
      custom_mappings/auto_mapping.json
      oraxen/items/*.yml  +  oraxen/pack/textures/*.png

      Les docs et wiki

      https://docs.oraxen.com/

    https://geysermc.org/wiki/geyser/custom-items/

    
    MADE BY PHIL24k
    Copyright

Dépendances :
    pip install pyyaml pillow
    (optionnel : pip install matplotlib  -> aperçu 3D)
"""
# ---------------------------------------------------------------- imports
import json, shutil, uuid, sys, tkinter as tk, yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict
from tkinter import ttk, filedialog, simpledialog, messagebox

try:
    from PIL import Image
except ImportError:
    print("⚠ pillow est requis :  pip install pillow")
    sys.exit(1)

# ---------------------------------------------------------------- aperçu 3D (facultatif)
try:
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def preview_cube(path: Path, title="Preview"):
    if not HAS_MPL:
        messagebox.showinfo("Aperçu indisponible",
                            "Installe pillow + matplotlib pour l’aperçu 3D.")
        return
    tex = plt.imread(path)
    fig = plt.figure(figsize=(3, 3))
    ax = fig.add_subplot(111, projection="3d")
    r = [-.5, .5]
    faces = [((.5, .5), r, r), ((-.5, -.5), r, r),
             (r, (.5, .5), r), (r, (-.5, -.5), r),
             (r, r, (.5, .5)), (r, r, (-.5, -.5))]
    for xs, ys, zs in faces:
        ax.plot_surface([[xs[0]] * 2, [xs[1]] * 2],
                        [[ys[0], ys[1]]] * 2,
                        [[zs[0], zs[0]], [zs[1], zs[1]]],
                        facecolors=tex, shade=False)
    ax.view_init(35, 30)
    ax.axis("off")
    plt.title(title)
    plt.show()


# ---------------------------------------------------------------- utilitaires
def convert_java_armor_to_bedrock(src: Path, dst: Path):
    """Bedrock accepte déjà les PNG 64×32 layer_1 / layer_2 : simple copie."""
    try:
        img = Image.open(src).convert("RGBA")
    except FileNotFoundError:
        print(f"[WARN] overlay manquant : {src}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst)


def _find_textures_root(png: Path) -> Path:
    """Remonte jusqu’au dossier “textures” (structure Oraxen)."""
    for p in png.parents:
        if p.name == "textures":
            return p
    raise FileNotFoundError("Dossier textures introuvable pour :" + str(png))


# ---------------------------------------------------------------- dataclasses
@dataclass
class Extras:
    unbreakable: bool = False
    attributes: Dict[str, float] = field(default_factory=dict)
    enchants: Dict[str, int] = field(default_factory=dict)
    lore: List[str] = field(default_factory=list)

    def to_yaml_lines(self) -> List[str]:
        out: List[str] = []
        if self.unbreakable:
            out.append("  unbreakable: true")
        if self.attributes:
            out.append("  attributes:")
            for k, v in self.attributes.items():
                out.append(f"    {k}: {v}")
        if self.enchants:
            out.append("  enchants:")
            for k, v in self.enchants.items():
                out.append(f"    {k}: {v}")
        if self.lore:
            out.append("  lore:")
            for l in self.lore:
                out.append(f"    - \"{l}\"")
        return out


@dataclass
class PackEntry:
    identifier: str
    display_name: str
    java_material: str
    cmd: int
    kind: str  # item | block | armor
    icon: Path
    armor_type: str = ""
    extras: Extras = field(default_factory=Extras)

    tex_base: str = ""  # chemin overlay (sans _layer_1)
    overlay_paths: List[str] = field(default_factory=list)


# ---------------------------------------------------------------- PackBuilder
class PackBuilder:
    def __init__(self, entries: List[PackEntry], out: Path,
                 skip_oraxen: bool = False):
        """
        :param entries:     objets à traiter
        :param out:         dossier de sortie
        :param skip_oraxen: True → on NE régénère PAS oraxen/
        """
        self.e = entries
        self.out = out
        self.skip_oraxen = skip_oraxen

    # ----- helpers dossier
    def _dir(self, *p):
        d = self.out.joinpath(*p)
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ----- mapping armure
    @staticmethod
    def _armor_meta(a_type: str):
        m = {
            "helmet": ("geometry.player.armor.helmet",
                       "v.helmet_layer_visible", "layer_1", "helmet"),
            "chestplate": ("geometry.player.armor.chestplate",
                           "v.chest_layer_visible", "layer_1", "chestplate"),
            "leggings": ("geometry.player.armor.leggings",
                         "v.leg_layer_visible", "layer_2", "leggings"),
            "boots": ("geometry.player.armor.boots",
                      "v.boot_layer_visible", "layer_1", "boots"),
        }
        return m[a_type]

    # ----- attachable
    def _write_attachable(self, root: Path, e: PackEntry):
        geo, vis_var, layer, fname = self._armor_meta(e.armor_type)
        tex_key = e.tex_base + f"_{layer}"
        tex_path = f"textures/models/armor/{Path(tex_key).name}"

        data = {
            "format_version": "1.12.0",
            "minecraft:attachable": {
                "description": {
                    "identifier": f"geyser_custom:{e.identifier}",
                    "materials": {
                        "default": "armor",
                        "enchanted": "armor_enchanted"
                    },
                    "textures": {
                        "default": tex_path,
                        "enchanted": "textures/misc/enchanted_actor_glint"
                    },
                    "geometry": {"default": geo},
                    "scripts": {"parent_setup": f"{vis_var} = 0.0;"},
                    "render_controllers": ["controller.render.armor"]
                }
            }
        }

        adir = root / "attachables" / e.identifier
        adir.mkdir(parents=True, exist_ok=True)
        (adir / f"{fname}.json").write_text(json.dumps(data, indent=2))

    # ----- pack Bedrock
    def _bedrock(self):
        root = self._dir("bedrock_pack")
        (root / "textures/items").mkdir(parents=True, exist_ok=True)

        manifest = {
            "format_version": 2,
            "header": {
                "description": "Auto Pack",
                "name": "Auto Pack",
                "uuid": str(uuid.uuid4()),
                "version": [1, 0, 0],
                "min_engine_version": [1, 20, 0]
            },
            "modules": [{
                "type": "resources",
                "uuid": str(uuid.uuid4()),
                "version": [1, 0, 0]
            }]
        }
        (root / "manifest.json").write_text(json.dumps(manifest, indent=2))

        atlas = {
            "resource_pack_name": "auto_generated_pack",
            "texture_name": "atlas.items",
            "texture_data": {}
        }

        for e in self.e:
            # icône
            atlas["texture_data"][e.identifier] = {
                "textures": f"textures/items/{e.identifier}"
            }
            shutil.copy(e.icon, root / "textures/items" /
                        f"{e.identifier}.png")

            # armure
            if e.kind == "armor":
                armor_dst = root / "textures/models/armor"
                armor_dst.mkdir(parents=True, exist_ok=True)

                tex_root = _find_textures_root(e.icon)
                for rel in e.overlay_paths:
                    src = tex_root / f"{rel}.png"
                    if not src.exists():
                        print(f"[WARN] overlay manquant {src}")
                        continue
                    dst = armor_dst / src.name
                    convert_java_armor_to_bedrock(src, dst)

                self._write_attachable(root, e)

        (root / "textures/item_texture.json").write_text(
            json.dumps(atlas, indent=2))
        return root

    # ----- pack Oraxen
    def _make_yaml(self, e: PackEntry) -> str:
        lines = [
            f"{e.identifier}:",
            f"  displayname: \"{e.display_name}\"",
            f"  material: {e.java_material}",
        ]
        if e.kind == "armor":
            lines += ["  armor:", f"    type: {e.armor_type}"]
        elif e.kind == "block":
            lines += ["  block:", "    hardness: 1.0"]
        lines += e.extras.to_yaml_lines()
        lines += [
            "  Pack:",
            f"    custom_model_data: {e.cmd}",
            "    generate_model: true",
            ('    parent_model: "item/handheld"'
             if e.kind in ("item", "armor")
             else '    parent_model: "item/generated"'),
            "    textures:",
            f"      - {e.identifier}.png",
            ""
        ]
        return "\n".join(lines)

    def _oraxen(self):
        root = self._dir("oraxen")
        tex_dir = self._dir("oraxen", "pack", "textures")
        items_d = self._dir("oraxen", "items")
        for e in self.e:
            shutil.copy(e.icon, tex_dir / f"{e.identifier}.png")
            (items_d / f"{e.identifier}.yml").write_text(self._make_yaml(e))
        return root

    # ----- mapping Geyser
    def _mapping(self):
        mp = {"format_version": 1, "items": {}}
        for e in self.e:
            base = f"minecraft:{e.java_material.lower()}"
            mp["items"].setdefault(base, []).append({
                "name": e.identifier,
                "custom_model_data": e.cmd,
                "display_name": e.display_name,
                "icon": e.identifier,
                "allow_offhand": False,
                "texture_size": 16
            })
        p = self._dir("custom_mappings") / "auto_mapping.json"
        p.write_text(json.dumps(mp, indent=2))
        return p

    # ----- point d’entrée
    def build(self):
        bed = self._bedrock()
        mp = self._mapping()
        ora = None
        if not self.skip_oraxen:
            ora = self._oraxen()
        return bed, ora, mp


# ---------------------------------------------------------------- GUI
class GeneratorGUI(ttk.Frame):
    ARMOR_TYPES = ("helmet", "chestplate", "leggings", "boots")

    def __init__(self, root: tk.Tk):
        super().__init__(root)
        self.pack(fill="both", expand=True)
        ttk.Style().theme_use("clam")
        root.title("Pack Generator v2.8")
        root.minsize(820, 620)

        # état
        self.icon = tk.StringVar()
        self.ident = tk.StringVar()
        self.name = tk.StringVar()
        self.material = tk.StringVar(value="DIAMOND_SWORD")
        self.cmd = tk.IntVar(value=1)
        self.kind = tk.StringVar(value="item")
        self.armor_type = tk.StringVar(value="helmet")
        self.unbreakable_var = tk.BooleanVar()
        self.outdir = tk.StringVar(value=str(Path.cwd()))

        self.entries: List[PackEntry] = []
        self.attributes: Dict[str, float] = {}
        self.enchants: Dict[str, int] = {}
        self.lore_list: List[str] = []

        self._build_ui()

    # ---------- UI
    def _build_ui(self):
        left, right = ttk.Frame(self, padding=10), ttk.Frame(self, padding=10)
        left.pack(side="left", fill="both", expand=True)
        right.pack(side="right", fill="y")

        def field(label, var, browse=""):
            fr = ttk.Frame(left); fr.pack(fill="x", pady=2)
            ttk.Label(fr, text=label, width=15).pack(side="left")
            ttk.Entry(fr, textvariable=var).pack(side="left", fill="x",
                                                 expand=True)
            if browse:
                fn = self._ask_file if browse == "file" else self._ask_dir
                ttk.Button(fr, text="…", width=3,
                           command=lambda v=var: fn(v)).pack(side="left")

        field("Icône PNG", self.icon, "file")
        field("ID interne", self.ident)
        field("Nom affiché", self.name)
        field("Matériel Java", self.material)
        field("CustomModelData", self.cmd)

        fr_kind = ttk.Frame(left); fr_kind.pack(fill="x", pady=2)
        ttk.Label(fr_kind, text="Type", width=15).pack(side="left")
        cb_kind = ttk.Combobox(fr_kind, textvariable=self.kind,
                               values=("item", "block", "armor"),
                               state="readonly", width=12)
        cb_kind.pack(side="left")
        cb_kind.bind("<<ComboboxSelected>>", self._toggle_armor)

        self.f_armor = ttk.Frame(left)
        ttk.Label(self.f_armor, text="Armor type",
                  width=15).pack(side="left")
        ttk.Combobox(self.f_armor, textvariable=self.armor_type,
                     values=self.ARMOR_TYPES, state="readonly",
                     width=12).pack(side="left")
        self._toggle_armor()

        # option skip_oraxen
        self.skip_oraxen_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(left,
                        text="Ne pas régénérer le dossier Oraxen",
                        variable=self.skip_oraxen_var
                        ).pack(anchor="w", pady=(4, 0))

        ttk.Separator(left).pack(fill="x", pady=6)
        ttk.Label(left, text="Extras (Oraxen)",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        ttk.Checkbutton(left, text="Unbreakable",
                        variable=self.unbreakable_var
                        ).pack(anchor="w", pady=2)

        extras_fr = ttk.Frame(left); extras_fr.pack(fill="x", pady=2)

        attr_fr = ttk.Labelframe(extras_fr, text="Attributs")
        attr_fr.pack(side="left", fill="both", expand=True, padx=(0, 4))
        self.attr_lb = tk.Listbox(attr_fr, height=4)
        self.attr_lb.pack(fill="both", expand=True)
        ttk.Button(attr_fr, text="+", width=3,
                   command=self._add_attribute).pack(side="left",
                                                     padx=2, pady=2)
        ttk.Button(attr_fr, text="-", width=3,
                   command=lambda: self._remove_selected(
                       self.attr_lb, self.attributes)
                   ).pack(side="left", pady=2)

        ench_fr = ttk.Labelframe(extras_fr, text="Enchantements")
        ench_fr.pack(side="left", fill="both", expand=True)
        self.ench_lb = tk.Listbox(ench_fr, height=4)
        self.ench_lb.pack(fill="both", expand=True)
        ttk.Button(ench_fr, text="+", width=3,
                   command=self._add_enchant).pack(side="left",
                                                   padx=2, pady=2)
        ttk.Button(ench_fr, text="-", width=3,
                   command=lambda: self._remove_selected(
                       self.ench_lb, self.enchants)
                   ).pack(side="left", pady=2)

        lore_fr = ttk.Labelframe(left, text="Lore")
        lore_fr.pack(fill="both", pady=4)
        self.lore_lb = tk.Listbox(lore_fr, height=4)
        self.lore_lb.pack(side="left", fill="both", expand=True)
        lore_entry = ttk.Entry(lore_fr)
        lore_entry.pack(side="left", fill="x", expand=True, padx=(4, 0))
        ttk.Button(lore_fr, text="Ajouter",
                   command=lambda: self._add_lore(lore_entry)
                   ).pack(side="left", padx=4)
        ttk.Button(lore_fr, text="Suppr",
                   command=lambda: self._remove_selected(
                       self.lore_lb, self.lore_list)
                   ).pack(side="left")

        field("Dossier sortie", self.outdir, "dir")

        btns = ttk.Frame(left); btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="Ajouter",
                   command=self._add_entry).pack(side="left")
        ttk.Button(btns, text="Importer dossier Oraxen",
                   command=self._import_oraxen).pack(side="left", padx=4)
        ttk.Button(btns, text="Aperçu 3D",
                   command=self._preview).pack(side="left", padx=4)
        ttk.Button(btns, text="Générer packs",
                   command=self._generate).pack(side="right")

        ttk.Label(right, text="Objets",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        self.item_lb = tk.Listbox(right, height=32)
        self.item_lb.pack(fill="y", expand=True)
        ttk.Button(right, text="Supprimer",
                   command=self._delete_item).pack(pady=4)

    # ---------- small helpers
    @staticmethod
    def _ask_file(var):
        p = filedialog.askopenfilename(filetypes=[("PNG", "*.png")])
        if p:
            var.set(p)

    @staticmethod
    def _ask_dir(var):
        p = filedialog.askdirectory()
        if p:
            var.set(p)

    def _toggle_armor(self, *_):
        self.f_armor.pack_forget()
        if self.kind.get() == "armor":
            self.f_armor.pack(fill="x", pady=2)

    # ---------- extras
    def _add_attribute(self):
        k = simpledialog.askstring("Attribut", "Nom (ex. attack_damage)")
        if not k:
            return
        v = simpledialog.askfloat("Attribut", f"Valeur pour {k}")
        if v is None:
            return
        self.attributes[k] = v
        self._refresh_lb(self.attr_lb, self.attributes)

    def _add_enchant(self):
        k = simpledialog.askstring("Enchantement", "Nom (ex. sharpness)")
        if not k:
            return
        v = simpledialog.askinteger("Enchantement", f"Niveau pour {k}")
        if v is None:
            return
        self.enchants[k] = v
        self._refresh_lb(self.ench_lb, self.enchants)

    def _add_lore(self, entry):
        text = entry.get().strip()
        if text:
            self.lore_list.append(text)
            self._refresh_lb(self.lore_lb, self.lore_list)
            entry.delete(0, "end")

    def _remove_selected(self, lb: tk.Listbox, backing):
        sel = list(lb.curselection())
        if not sel:
            return
        for i in reversed(sel):
            key = (lb.get(i).split(":")[0] if isinstance(backing, dict)
                   else lb.get(i))
            if isinstance(backing, dict):
                backing.pop(key, None)
            else:
                backing.remove(key)
            lb.delete(i)

    @staticmethod
    def _refresh_lb(lb: tk.Listbox, backing):
        lb.delete(0, "end")
        if isinstance(backing, dict):
            for k, v in backing.items():
                lb.insert("end", f"{k}: {v}")
        else:
            for s in backing:
                lb.insert("end", s)

    # ---------- ajout entrée manuelle
    def _add_entry(self):
        if not Path(self.icon.get()).exists():
            messagebox.showerror("Erreur", "Icône PNG introuvable.")
            return
        if not self.ident.get().strip():
            messagebox.showerror("Erreur", "ID manquant.")
            return

        entry = PackEntry(
            identifier=self.ident.get().strip().lower(),
            display_name=(self.name.get().strip()
                          or self.ident.get().replace("_", " ").title()),
            java_material=self.material.get().strip().upper(),
            cmd=int(self.cmd.get()),
            kind=self.kind.get(),
            icon=Path(self.icon.get()),
            armor_type=self.armor_type.get(),
            extras=Extras(
                unbreakable=self.unbreakable_var.get(),
                attributes=self.attributes.copy(),
                enchants=self.enchants.copy(),
                lore=self.lore_list.copy()
            )
        )
        self.entries.append(entry)
        self.item_lb.insert("end",
                            f"{entry.kind}:{entry.identifier} ({entry.java_material})")

        # reset rapides
        self.ident.set("")
        self.name.set("")
        self.attributes.clear()
        self.enchants.clear()
        self.lore_list.clear()
        self._refresh_lb(self.attr_lb, self.attributes)
        self._refresh_lb(self.ench_lb, self.enchants)
        self._refresh_lb(self.lore_lb, self.lore_list)
        self.unbreakable_var.set(False)

    def _delete_item(self):
        for i in reversed(self.item_lb.curselection()):
            self.item_lb.delete(i)
            del self.entries[i]

    # ---------- preview / generate
    def _preview(self):
        if Path(self.icon.get()).exists():
            preview_cube(Path(self.icon.get()),
                         self.ident.get() or "Preview")

    def _generate(self):
        if not self.entries:
            messagebox.showerror("Erreur", "Liste vide.")
            return

        out = Path(self.outdir.get())
        out.mkdir(exist_ok=True)

        bed, ora, mp = PackBuilder(
            self.entries, out,
            skip_oraxen=self.skip_oraxen_var.get()
        ).build()

        msg = [f"Bedrock pack : {bed}", f"Mapping      : {mp}"]
        if ora:
            msg.append(f"Oraxen pack  : {ora}")
        messagebox.showinfo("Succès", "\n".join(msg))

    # ---------- import Oraxen
    def _import_oraxen(self):
        root = filedialog.askdirectory(title="Dossier plugins/Oraxen")
        if not root:
            return
        items_dir = Path(root) / "items"
        tex_dir = Path(root) / "pack" / "textures"
        if not items_dir.exists():
            messagebox.showerror("Erreur", "items/ introuvable")
            return

        count = skipped = 0
        for yml in items_dir.glob("*.yml"):
            try:
                cfg = yaml.safe_load(yml.read_text(encoding="utf-8"))
            except Exception as ex:
                print(f"[WARN] YAML invalide {yml}: {ex}")
                continue
            if not isinstance(cfg, dict):
                continue

            for ident, section in cfg.items():
                try:
                    pack_cfg = section["Pack"]
                    material = section["material"]
                    cmd = int(pack_cfg["custom_model_data"])

                    tex_raw = pack_cfg["textures"]
                    ico_rel = tex_raw[0] if isinstance(
                        tex_raw, list) else tex_raw
                    icon_png = (tex_dir / ico_rel).with_suffix(".png")
                    if not icon_png.exists():
                        raise FileNotFoundError(icon_png)

                    mat_u = material.upper()
                    is_armor = ("armor" in section or
                                mat_u.endswith(("_HELMET", "_CHESTPLATE",
                                                "_LEGGINGS", "_BOOTS")))

                    if is_armor:
                        folder = icon_png.parent
                        stem = icon_png.stem
                        base = (stem.rsplit("_", 1)[0] if stem.endswith((
                                "_helmet", "_chestplate",
                                "_leggings", "_boots")) else stem)
                        layer1 = next(folder.glob(f"{base}*layer_1.png"), None)
                        layer2 = next(folder.glob(f"{base}*layer_2.png"), None)
                        if not (layer1 and layer2):
                            raise FileNotFoundError(
                                "layers manquants pour " + ident)

                        overlay_paths = [
                            layer1.relative_to(tex_dir).with_suffix("").as_posix(),
                            layer2.relative_to(tex_dir).with_suffix("").as_posix()
                        ]
                        a_type = (section.get("armor", {})
                                  .get("type", material.split("_")[-1].lower()))
                        kind = "armor"
                    elif "block" in section:
                        kind, a_type = "block", ""
                        overlay_paths = [Path(
                            ico_rel).with_suffix("").as_posix()]
                    else:
                        kind, a_type = "item", ""
                        overlay_paths = [Path(
                            ico_rel).with_suffix("").as_posix()]

                    entry = PackEntry(
                        identifier=ident,
                        display_name=section.get("displayname", ident),
                        java_material=material,
                        cmd=cmd,
                        kind=kind,
                        armor_type=a_type,
                        icon=icon_png,
                        tex_base=(overlay_paths[0].rsplit("_layer_", 1)[0]
                                  if is_armor else overlay_paths[0]),
                        overlay_paths=overlay_paths
                    )
                    self.entries.append(entry)
                    self.item_lb.insert("end",
                                        f"{entry.kind}:{entry.identifier} "
                                        f"({entry.java_material})")
                    count += 1
                except Exception as ex:
                    print(f"[WARN] {yml} > {ident}: {ex}")
                    skipped += 1

        messagebox.showinfo("Import terminé",
                            f"{count} items importés – {skipped} ignorés.")


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    root = tk.Tk()
    GeneratorGUI(root)
    root.mainloop()

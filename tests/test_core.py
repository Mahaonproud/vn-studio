import os, sys, tempfile, unittest, shutil, re, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vnstudio.core.model import Project, Step, apply_step, SceneState, list_projects
from vnstudio.core import assets as A
from vnstudio.core.check import validate, collect_usage
from vnstudio.core.exporter import export_project, rpy
from vnstudio.core.util import write_png, image_size, slug, hex_alpha
from vnstudio.core.spell import SpellContext, Speller


def make_png(path, w, h, color=(200, 50, 50, 255)):
    write_png(path, w, h, bytes(color) * (w * h))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.src = self.tmp / "src"
        self.src.mkdir()
        self.p = Project.create("Тестовая новелла", self.tmp / "projects")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make_assets(self):
        make_png(self.src / "forest.png", 64, 36)
        make_png(self.src / "room.png", 64, 36)
        make_png(self.src / "hira_happy.png", 40, 100)
        make_png(self.src / "hira_sad.png", 40, 120)
        (self.src / "theme.ogg").write_bytes(b"OggS" + b"0" * 20)
        make_png(self.src / "load.png", 64, 36)
        bg1 = A.import_asset(self.p, "backgrounds", self.src / "forest.png")
        bg2 = A.import_asset(self.p, "backgrounds", self.src / "room.png")
        mu = A.import_asset(self.p, "music", self.src / "theme.ogg")
        ld = A.import_asset(self.p, "loading", self.src / "load.png")
        ch = A.add_character(self.p, "Хира")
        A.add_emotion(self.p, ch, "happy", self.src / "hira_happy.png")
        A.add_emotion(self.p, ch, "грустная", self.src / "hira_sad.png")
        return bg1, bg2, mu, ld, ch


class TestUtil(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(slug("Хира Тян"), "hira_tyan")
        self.assertEqual(slug("123 лес"), "n123_les")
        self.assertEqual(slug("!!!"), "x")
    def test_hex(self):
        self.assertEqual(hex_alpha("#FF0000", 100), "#ff0000ff")
        self.assertEqual(hex_alpha("#f00", 0), "#ff000000")
    def test_rpy(self):
        self.assertEqual(rpy('Он сказал: "привет" [x] {i}'), 'Он сказал: \\"привет\\" [[x] {{i}')
        self.assertEqual(rpy("a\nb"), "a\\nb")
    def test_image_size_png_and_jpeg(self):
        from PIL import Image
        d = Path(tempfile.mkdtemp())
        try:
            make_png(d / "a.png", 33, 17)
            self.assertEqual(tuple(image_size(d / "a.png")), (33, 17))
            im = Image.new("RGB", (123, 45), (10, 20, 30))
            for ext, fmt in (("jpg", "JPEG"), ("webp", "WEBP"), ("gif", "GIF"), ("bmp", "BMP")):
                im.save(d / f"a.{ext}", fmt)
                self.assertEqual(tuple(image_size(d / f"a.{ext}")), (123, 45), ext)
            im.save(d / "l.webp", "WEBP", lossless=True)
            self.assertEqual(tuple(image_size(d / "l.webp")), (123, 45), "webp lossless")
        finally:
            shutil.rmtree(d)


class TestModel(Base):
    def test_save_load_roundtrip(self):
        bg1, bg2, mu, ld, ch = self.make_assets()
        b = self.p.add_block("Диалог 1")
        b.steps.append(Step.new("bg", {"asset": bg1.id, "clear": True}))
        b.steps.append(Step.new("say", {"who": "", "text": "Привет"}))
        self.p.save()
        q = Project.load(self.p.root)
        self.assertEqual(q.name, "Тестовая новелла")
        self.assertEqual(len(q.blocks), 1)
        self.assertEqual(q.blocks[0].steps[1].data["text"], "Привет")
        self.assertEqual(len(q.assets["backgrounds"]), 2)
        self.assertEqual(q.characters[0].name, "Хира")
        self.assertEqual(len(q.menu.buttons), 5)
        self.assertEqual(len(list_projects(self.tmp / "projects")), 1)

    def test_state_and_branches(self):
        bg1, bg2, mu, ld, ch = self.make_assets()
        b = self.p.add_block("Диалог 1")
        b.steps.append(Step.new("bg", {"asset": bg1.id, "clear": True}))
        b.steps.append(Step.new("show", {"char": ch.id, "emotion": "happy", "pos": "left"}))
        choice = Step.new("choice", {"options": []})
        b.steps.append(choice)
        k1 = self.p.add_block("Ответ 1", b.id, choice.id)
        k2 = self.p.add_block("Ответ 2", b.id, choice.id)
        choice.data["options"] = [{"text": "да", "block": k1.id}, {"text": "нет", "block": k2.id}]
        k1.steps.append(Step.new("show", {"char": ch.id, "emotion": "грустная"}))
        st = self.p.state_at(k1.id, 1)
        self.assertEqual(st.bg, bg1.id)
        self.assertEqual(st.chars[ch.id], ("грустная", "left"))
        self.assertEqual([x.id for x in self.p.children_of(b.id)], [k1.id, k2.id])
        self.assertEqual(self.p.root_of(k2).id, b.id)
        self.p.remove_block_tree(k1.id)
        self.assertIsNone(self.p.block(k1.id))

    def test_undo_snapshot(self):
        b = self.p.add_block("A")
        snap = self.p.snapshot_blocks()
        b.steps.append(Step.new("say", {"text": "x"}))
        self.p.add_block("B")
        self.p.restore_blocks(snap)
        self.assertEqual(len(self.p.blocks), 1)
        self.assertEqual(len(self.p.blocks[0].steps), 0)


class TestAssets(Base):
    def test_builtin_effects(self):
        t = time.time()
        n = A.add_builtin_effects(self.p)
        dt = time.time() - t
        print(f"builtin effects: {n} in {dt:.1f}s")
        self.assertEqual(n, 7)
        self.assertEqual(A.add_builtin_effects(self.p), 0)
        for a in self.p.assets["effects"]:
            if a.kind == "image":
                self.assertTrue(self.p.abs(a.file).exists())
                self.assertEqual(tuple(image_size(self.p.abs(a.file))), (960, 540))
        from PIL import Image
        for a in self.p.assets["effects"]:
            if a.kind == "image":
                im = Image.open(self.p.abs(a.file)); im.load()
                self.assertEqual(im.mode, "RGBA")
                alpha = im.getchannel("A")
                self.assertGreater(alpha.getextrema()[1], 10, a.name)

    def test_bulk_import(self):
        root = self.tmp / "pack"
        (root / "Фоны").mkdir(parents=True)
        (root / "музыка").mkdir()
        (root / "Персонажи" / "Хира").mkdir(parents=True)
        (root / "Персонажи" / "Рен").mkdir(parents=True)
        make_png(root / "Фоны" / "лес.png", 10, 10)
        make_png(root / "Фоны" / "комната.jpg".replace("jpg", "png"), 10, 10)
        (root / "музыка" / "тема.mp3").write_bytes(b"ID3" + b"0" * 10)
        (root / "музыка" / "заметки.txt").write_text("не звук")
        make_png(root / "Персонажи" / "Хира" / "улыбка.png", 10, 20)
        make_png(root / "Персонажи" / "Хира" / "грусть.png", 10, 20)
        make_png(root / "Персонажи" / "Рен" / "обычный.png", 10, 20)
        calls = []
        s = A.bulk_import(self.p, root, lambda i, n, t: calls.append((i, n)))
        self.assertEqual(s["backgrounds"], 2)
        self.assertEqual(s["music"], 1)
        self.assertEqual(s["characters"], 2)
        self.assertEqual(len(self.p.get_char("ch1").emotions) + len(self.p.get_char("ch2").emotions), 3)
        self.assertTrue(calls)
        s2 = A.bulk_import(self.p, root)
        self.assertEqual(s2["backgrounds"], 0)
        self.assertEqual(s2["skipped"], 6)
        empty = self.tmp / "empty"; empty.mkdir()
        with self.assertRaises(ValueError):
            A.bulk_import(self.p, empty)

    def test_bad_ext(self):
        f = self.src / "x.txt"; f.write_text("x")
        with self.assertRaises(ValueError):
            A.import_asset(self.p, "backgrounds", f)

    def test_remove(self):
        bg1, *_ = self.make_assets()
        path = self.p.abs(bg1.file)
        self.assertTrue(path.exists())
        A.remove_asset(self.p, bg1.id)
        self.assertFalse(path.exists())
        self.assertIsNone(self.p.find_asset(bg1.id))


class TestExport(Base):
    def build(self):
        bg1, bg2, mu, ld, ch = self.make_assets()
        A.add_builtin_effects(self.p)
        fx = {a.params["builtin"]: a for a in self.p.assets["effects"]}
        b = self.p.add_block("Диалог 1")
        b.steps += [
            Step.new("bg", {"asset": bg1.id, "clear": True, "trans": "fade"}),
            Step.new("music", {"asset": mu.id}),
            Step.new("say", {"who": "", "text": 'Какая сегодня "хорошая" погода?'}),
            Step.new("show", {"char": ch.id, "emotion": "happy", "pos": "left"}),
            Step.new("say", {"who": ch.id, "text": "Привет!\nКак дела? [x] {b}"}),
            Step.new("fx_on", {"asset": fx["blood"].id}),
            Step.new("fx_on", {"asset": fx["tint_red"].id}),
            Step.new("fx_once", {"asset": fx["shake"].id}),
            Step.new("show", {"char": ch.id, "emotion": "грустная"}),
            Step.new("fx_off", {"asset": fx["blood"].id}),
            Step.new("bg", {"asset": bg2.id}),
        ]
        choice = Step.new("choice", {})
        b.steps.append(choice)
        k1 = self.p.add_block("Ответ 1", b.id, choice.id)
        k2 = self.p.add_block("Ответ 2", b.id, choice.id)
        k3 = self.p.add_block("Ответ 3", b.id, choice.id)
        choice.data["options"] = [{"text": "Да", "block": k1.id}, {"text": "Нет", "block": k2.id},
                                  {"text": "Не знаю", "block": k3.id}]
        k1.steps += [Step.new("say", {"who": ch.id, "text": "Хорошо"}), Step.new("hide", {"char": ch.id})]
        k1.shared_end = True
        k2.steps += [Step.new("say", {"who": ch.id, "text": "Жаль"})]
        k2.link_to = k1.id
        k3.steps += [Step.new("say", {"who": "", "text": "Плохо"}), Step.new("ending", {"title": "Плохая концовка"})]
        b2 = self.p.add_block("Диалог 2")
        b2.steps += [Step.new("bg", {"asset": bg2.id, "clear": True}), Step.new("say", {"text": "Следующий день"}),
                     Step.new("music_stop", {})]
        self.p.menu.bg = ""
        self.p.menu.music = mu.id
        self.p.menu.loading = [{"asset": ld.id, "seconds": 2.5}]
        self.p.menu.effects = [fx["vignette"].id]
        self.p.menu.title = 'Моя "игра"'
        return b, b2, k1, k2, k3, ch

    def test_validate_ok(self):
        self.build()
        issues = [i for i in validate(self.p) if i.level == "error"]
        self.assertEqual(issues, [])

    def test_validate_errors(self):
        b, b2, k1, k2, k3, ch = self.build()
        A.remove_character(self.p, ch.id)
        k1.link_to = k1.id
        msgs = " | ".join(i.text for i in validate(self.p) if i.level == "error")
        self.assertIn("удалённый персонаж", msgs)
        self.assertIn("сам с собой", msgs)

    def test_export(self):
        b, b2, k1, k2, k3, ch = self.build()
        game = self.tmp / "game"
        rep = export_project(self.p, game)
        self.assertEqual(rep.warnings, [])
        script = (game / "script.rpy").read_text("utf-8")
        setup = (game / "vn_setup.rpy").read_text("utf-8")
        menu = (game / "vn_menu.rpy").read_text("utf-8")
        print("\n----- script.rpy -----\n" + script)
        print("----- vn_setup.rpy -----\n" + setup)
        print("----- vn_menu.rpy -----\n" + menu)
        self.assertIn("label start:\n    jump vn_" + b.id, script)
        self.assertIn('scene bg forest with fade', script) if 'bg forest' in script else self.assertIn("scene bg ", script)
        self.assertIn('\\"хорошая\\"', script)
        self.assertIn("[[x]", script)
        self.assertIn("{{b}", script)
        self.assertIn("thought \"", script)
        self.assertIn("with vpunch", script)
        self.assertIn("menu:", script)
        self.assertIn(f"jump vn_{k1.id}", script)
        self.assertIn("centered \"Плохая концовка\"", script)
        self.assertIn("label splashscreen:", script)
        # k2 связан с k1; k1 заканчивается переходом ко 2-му диалогу
        blk = lambda bid: script.split(f"label vn_{bid}:")[1].split("\n\n")[0]
        self.assertIn(f"jump vn_{k1.id}", blk(k2.id))
        self.assertIn(f"jump vn_{b2.id}", blk(k1.id))
        self.assertTrue(blk(b2.id).rstrip().endswith("return"))
        # второе show (смена эмоции) не должно повторять "at left"
        shows = [l for l in script.splitlines() if l.strip().startswith("show ch_")]
        self.assertEqual(len(shows), 2)
        self.assertIn("at left", shows[0])
        self.assertNotIn(" at ", shows[1])
        # bg2 в середине диалога — show, а не scene
        self.assertTrue(any(l.strip().startswith("show bg ") for l in script.splitlines()))
        self.assertIn("zoom=", setup)
        self.assertIn("style say_dialogue:", setup)
        self.assertIn('background Solid("#000000', setup)
        self.assertIn("screen main_menu():", menu)
        self.assertIn("config.main_menu_music", menu)
        self.assertIn('textbutton "Играть":', menu)
        self.assertIn("Quit(confirm=False)", menu)
        self.assertIn('text "Моя \\"игра\\""', menu)
        # файлы скопированы
        for sub in ("bg", "chars", "audio", "fx", "loading"):
            self.assertTrue(any((game / "vn_assets" / sub).iterdir()), sub)
        self.check_rpy_structure(script)
        self.check_rpy_structure(setup)
        self.check_rpy_structure(menu)

    def check_rpy_structure(self, text):
        in_label = False
        for n, line in enumerate(text.splitlines(), 1):
            if not line.strip() or line.startswith("#"):
                continue
            indent = len(line) - len(line.lstrip(" "))
            self.assertEqual(indent % 4, 0, f"line {n}: {line!r}")
            if indent == 0:
                in_label = line.startswith("label ")
            self.assertEqual(line.count('"') - line.count('\\"') * 1 - 2 * line.count('\\\\"') % 2, line.count('"') - line.count('\\"'), f"quotes {n}")
            q = len(re.findall(r'(?<!\\)"', line))
            self.assertEqual(q % 2, 0, f"unbalanced quotes line {n}: {line!r}")
            if in_label and indent == 0 and not line.startswith("label "):
                self.fail(f"top-level statement inside label: {line!r}")

    def test_export_missing_file_warns(self):
        b, b2, k1, k2, k3, ch = self.build()
        for a in self.p.assets["backgrounds"]:
            self.p.abs(a.file).unlink()
        rep = export_project(self.p, self.tmp / "game2")
        self.assertTrue(any("фон" in w.lower() for w in rep.warnings))
        self.assertTrue((self.tmp / "game2" / "script.rpy").exists())

    def test_reexport_cleans(self):
        self.build()
        game = self.tmp / "game3"
        export_project(self.p, game)
        stale = game / "vn_assets" / "bg" / "stale.png"
        stale.write_bytes(b"x")
        export_project(self.p, game)
        self.assertFalse(stale.exists())


class FakeSpell:
    words = {"привет", "как", "дела", "погода", "хорошая", "сегодня"}
    def __contains__(self, w): return w in self.words
    def candidates(self, w): return {"погода"} if w == "пагода" else None
    def word_usage_frequency(self, w): return 1.0
    def __getitem__(self, w): return 1


class TestSpell(Base):
    def ctx(self):
        c = SpellContext(self.p, "ru")
        sp = Speller.__new__(Speller)
        sp.lang = "ru"; sp.sp = FakeSpell(); sp.error = ""
        c.speller = sp
        return c

    def test_errors_and_suggest(self):
        c = self.ctx()
        text = "Привет, как дела? Сегодня пагода Хира XYZ"
        ch = A.add_character(self.p, "Хира")
        errs = c.errors(text)
        words = [w for _, _, w in errs]
        self.assertIn("пагода", words)
        self.assertNotIn("Хира", words)          # имя персонажа
        self.assertEqual(c.suggest("Пагода"), ["Погода"])
        s, e, w = [x for x in errs if x[2] == "пагода"][0]
        self.assertEqual(text[s:e], "пагода")
        c.ignore_word("пагода")
        self.assertNotIn("пагода", [w for _, _, w in c.errors(text)])
        self.assertIn("пагода", self.p.ignored)

    def test_unavailable(self):
        c = SpellContext(self.p, "xx")
        self.assertEqual(c.errors("пагода"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

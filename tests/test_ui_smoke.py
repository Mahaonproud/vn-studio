"""Дымовой тест интерфейса на имитации Qt: выполняет реальный код страниц и обработчиков."""
import shutil, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fakeqt
fakeqt.install()

from vnstudio.core import assets as A
from vnstudio.core.model import Project, Step
from vnstudio.core.settings import Settings
from vnstudio.core.util import write_png
from vnstudio.ui.workspace import Workspace


def png(path, w=32, h=18):
    write_png(path, w, h, bytes((10, 20, 30, 255)) * (w * h))


class Smoke(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.src = self.tmp / "src"
        self.src.mkdir()
        for n in ("lesA", "komnata"):
            png(self.src / f"{n}.png")
        png(self.src / "hira.png", 20, 50)
        png(self.src / "hira2.png", 20, 50)
        png(self.src / "load.png")
        (self.src / "t.ogg").write_bytes(b"OggS" + b"0" * 10)
        p = Project.create("Тест", self.tmp / "pr")
        A.add_builtin_effects(p)
        A.import_asset(p, "backgrounds", self.src / "lesA.png", "Лес")
        A.import_asset(p, "backgrounds", self.src / "komnata.png", "Комната")
        A.import_asset(p, "music", self.src / "t.ogg", "Тема")
        A.import_asset(p, "loading", self.src / "load.png", "Загрузка")
        c = A.add_character(p, "Хира")
        A.add_emotion(p, c, "радость", self.src / "hira.png")
        A.add_emotion(p, c, "грусть", self.src / "hira2.png")
        self.p = p
        s = Settings()
        s.projects_dir = str(self.tmp / "pr")
        self.ws = Workspace(p, s)
        self.ed = self.ws.editor
        fakeqt.ANSWERS.clear()
        fakeqt.LOG.clear()

    def tearDown(self):
        fakeqt.DIALOG_HOOK[0] = None
        shutil.rmtree(self.tmp, ignore_errors=True)

    def hook(self, fn):
        def h(dlg):
            fn(dlg)
            dlg.accept()
        fakeqt.DIALOG_HOOK[0] = h

    def make_dialog(self):
        def f(d):
            d.cb_bg.setCurrentIndex(1)
            d.cb_music.setCurrentIndex(1)
            d.picker.cb_char.setCurrentIndex(1)
        self.hook(f)
        self.ed.new_dialog()
        return self.ed.cur_block()

    def test_full_flow(self):
        ed, p = self.ed, self.p
        b = self.make_dialog()
        self.assertEqual([s.kind for s in b.steps], ["bg", "music", "show", "say"])
        self.assertEqual(ed.timeline.currentRow(), 3)
        self.assertEqual(ed.stack.currentIndex(), 1)
        self.assertEqual(b.steps[2].data["char"], "ch1")
        self.assertEqual(b.steps[3].data["who"], "ch1")
        # печатаем и жмём «Далее»
        ed.text.setPlainText("Какая сегодня хорошая погода?")
        self.assertEqual(b.steps[3].data["text"], "Какая сегодня хорошая погода?")
        ed.next_phrase()
        self.assertEqual(len(b.steps), 5)
        self.assertEqual(b.steps[4].data["who"], "ch1")
        ed.set_speaker("")
        ed.text.setPlainText("Мысли героя")
        self.assertEqual(b.steps[4].data["who"], "")
        # фон, эмоция, эффекты
        self.hook(lambda d: (d.cb.setCurrentIndex(1), d.chk.setChecked(False)))
        ed.add_bg()
        self.assertEqual(b.steps[5].kind, "bg")
        self.assertEqual(b.steps[5].data["asset"], p.assets["backgrounds"][1].id)
        self.hook(lambda d: d.picker.cb_emo.setCurrentIndex(1) if hasattr(d, "picker") else None)
        def pick_emotion(d):
            for w in d._extra if hasattr(d, "_extra") else []:
                pass
        # персонаж: BaseDialog с CharPicker — найдём picker через layout
        def show_hook(d):
            pk = [it.w for it in d.root._items if it.w is not None and hasattr(it.w, "cb_emo")][0]
            pk.cb_emo.setCurrentIndex(1)
        self.hook(show_hook)
        ed.add_show()
        self.assertEqual(b.steps[6].kind, "show")
        self.assertEqual(b.steps[6].data["emotion"], "грусть")
        fx = {a.params.get("builtin"): a for a in p.assets["effects"]}
        names = [a.id for a in p.assets["effects"]]
        self.hook(lambda d: d.combo.setCurrentIndex(names.index(fx["blood"].id)))
        ed.add_fx()
        self.assertEqual(b.steps[7].kind, "fx_on")
        self.hook(lambda d: d.combo.setCurrentIndex(names.index(fx["shake"].id)))
        ed.add_fx()
        self.assertEqual(b.steps[8].kind, "fx_once")
        self.hook(lambda d: None)
        ed.add_fx_off()
        self.assertEqual(b.steps[9].kind, "fx_off")
        self.hook(lambda d: None)
        ed.add_hide()
        self.assertEqual(b.steps[10].kind, "hide")
        self.hook(lambda d: d.combo.setCurrentIndex(0))
        ed.add_music()
        self.assertEqual(b.steps[11].kind, "music_stop")
        # состояние сцены в превью
        ed.timeline.setCurrentRow(7)
        self.assertIn(fx["blood"].id, ed.preview.state.fx)
        ed.timeline.setCurrentRow(10)
        self.assertEqual(ed.preview.state.chars, {})
        # перемещение и удаление
        ed.timeline.setCurrentRow(11)
        ed.move_step(-1)
        self.assertEqual(b.steps[10].kind, "music_stop")
        ed.delete_step()
        self.assertEqual(len(b.steps), 11)
        # варианты ответа
        ed.timeline.setCurrentRow(len(b.steps) - 1)
        def choice(d):
            for e, t in zip(d.edits, ["Да", "Нет", "Не знаю", ""]):
                e.setText(t)
        self.hook(choice)
        ed.add_choice()
        top = b
        kids = p.children_of(top.id)
        self.assertEqual(len(kids), 3)
        self.assertEqual(ed.cur_block().id, kids[0].id)
        self.assertTrue(ed.bar.isVisible())
        self.assertEqual(top.steps[-1].kind, "choice")
        # нельзя добавить второй выбор
        ed.select_block(top.id)
        n = len(p.blocks)
        ed.add_choice()
        self.assertEqual(len(p.blocks), n)
        # ветка 1: фраза, делаем конечной
        ed.select_block(kids[0].id)
        ed.add_say()
        ed.text.setPlainText("Хорошо, пойдём")
        ed.btn_shared.setChecked(True)
        self.assertTrue(kids[0].shared_end)
        # ветка 2: пишем и связываем
        ed.select_block(kids[1].id)
        ed.add_say()
        ed.text.setPlainText("Жаль")
        self.hook(lambda d: d.combo.setCurrentIndex(0))
        ed.link_to_shared()
        self.assertEqual(kids[1].link_to, kids[0].id)
        ed.unlink()
        self.assertEqual(kids[1].link_to, "")
        # ветка 3 + «связать остальные»
        ed.select_block(kids[2].id)
        ed.add_say()
        ed.text.setPlainText("Не знаю")
        ed.select_block(kids[0].id)
        ed.link_all_here()
        self.assertEqual(kids[1].link_to, kids[0].id)
        self.assertEqual(kids[2].link_to, kids[0].id)
        # конец игры в ветке и запрет добавить вариант после него
        ed.select_block(kids[2].id)
        fakeqt.ANSWERS["text"] = ("Плохая концовка", True)
        ed.add_ending()
        self.assertEqual(kids[2].steps[-1].kind, "ending")
        # правка вариантов: переименование и удаление
        ed.select_block(top.id)
        ed.timeline.setCurrentRow(len(top.steps) - 1)
        self.assertEqual(ed.stack.currentIndex(), 3)
        ed.on_option_text(0, "Конечно да")
        self.assertIn("Конечно да", kids[0].title)
        ed.add_option()
        self.assertEqual(len(p.children_of(top.id)), 4)
        ed.remove_option(3)
        self.assertEqual(len(p.children_of(top.id)), 3)
        # отмена / повтор
        before = len(p.blocks)
        ed.delete_block()  # top -> удаляем весь диалог (вопрос = Yes)
        self.assertEqual(len(p.blocks), 0)
        self.ws.undo()
        self.assertEqual(len(p.blocks), before)
        self.ws.redo()
        self.assertEqual(len(p.blocks), 0)
        self.ws.undo()
        self.assertEqual(len(p.blocks), before)
        # переименование
        top = p.block(top.id)
        fakeqt.ANSWERS["text"] = ("Пролог", True)
        ed.select_block(top.id)
        ed.rename_block()
        self.assertEqual(top.title, "Пролог")
        # сохранение + экспорт
        rep = self.ws.save()
        self.assertIsNotNone(rep)
        script = (self.p.root / "renpy_export" / "game" / "script.rpy").read_text("utf-8")
        self.assertIn("label start:", script)
        self.assertIn("menu:", script)
        self.assertFalse(self.ws.dirty)
        self.assertEqual(rep.warnings, [])

    def test_pages(self):
        ws, p = self.ws, self.p
        self.make_dialog()
        for name in ("library", "menu", "style", "export", "editor"):
            ws.show_page(name)
        lib = ws.library
        for i in range(lib.cats.count()):
            lib.cats.setCurrentRow(i)
        # библиотека: добавление файлов, переименование, удаление
        lib.cats.setCurrentRow(0)
        png(self.src / "new.png")
        fakeqt.ANSWERS["files"] = [str(self.src / "new.png")]
        lib.add_more()
        self.assertEqual(len(p.assets["backgrounds"]), 3)
        lib.grid.setCurrentRow(0)
        fakeqt.ANSWERS["text"] = ("Лес ночью", True)
        lib.rename()
        self.assertEqual(p.assets["backgrounds"][0].name, "Лес ночью")
        lib.remove()
        self.assertEqual(len(p.assets["backgrounds"]), 2)
        # персонажи
        lib.cats.setCurrentRow(1)
        fakeqt.ANSWERS["text"] = ("Рен", True)
        lib.add_more()
        self.assertEqual(len(p.characters), 2)
        lib.grid.setCurrentRow(1)
        lib.edit_item()
        # встроенные эффекты
        lib.cats.setCurrentRow(2)
        lib.add_builtin()
        # массовая загрузка
        root = self.tmp / "pack"
        (root / "фоны").mkdir(parents=True)
        png(root / "фоны" / "двор.png")
        fakeqt.ANSWERS["dir"] = str(root)
        lib.bulk()
        self.assertTrue(any(a.name == "двор" for a in p.assets["backgrounds"]))
        # меню игры
        m = ws.menu
        before = len(p.menu.buttons)
        m.add_button()
        self.assertEqual(len(p.menu.buttons), before + 1)
        m.lst_btn.setCurrentRow(m.lst_btn.count() - 1)
        m.ed_label.setText("Галерея")
        self.assertEqual(p.menu.buttons[-1]["label"], "Галерея")
        item = m.items[p.menu.buttons[-1]["id"]]
        item.setPos(300, 400)
        item.mouseReleaseEvent(None)
        self.assertEqual((p.menu.buttons[-1]["x"], p.menu.buttons[-1]["y"]), (300, 400))
        m.delete_button()
        self.assertEqual(len(p.menu.buttons), before)
        m.cb_music.setCurrentIndex(1)
        self.assertEqual(p.menu.music, p.assets["music"][0].id)
        m.ed_title.setText("Моя игра")
        self.assertEqual(p.menu.title, "Моя игра")
        self.hook(lambda d: None)
        m.add_loading()
        self.assertEqual(len(p.menu.loading), 1)
        m.add_fx()
        self.assertEqual(len(p.menu.effects), 1)
        m.remove_fx()
        m.remove_loading()
        m.reset_layout()
        # оформление текста
        st = ws.style_page
        st.size.setValue(48)
        st.kern.setValue(2.5)
        st.op.setValue(80)
        st.thought.setChecked(False)
        st.box_on.setChecked(False)
        self.assertEqual((p.style.size, p.style.kerning, p.style.opacity), (48, 2.5, 80))
        self.assertFalse(p.style.thought_italic)
        st.reset_font()
        # экспорт
        ex = ws.export
        ex.check()
        ex.save_and_export()
        game = p.root / "renpy_export" / "game"
        self.assertTrue((game / "vn_menu.rpy").exists())
        target = self.tmp / "renpy_proj" / "game"
        target.mkdir(parents=True)
        fakeqt.ANSWERS["dir"] = str(self.tmp / "renpy_proj")
        ex.export_to_renpy()
        self.assertTrue((target / "script.rpy").exists())
        self.assertTrue((target / "vn_assets").exists())

    def test_spell_strip_and_undo_text(self):
        ed = self.ed
        self.make_dialog()
        from vnstudio.core.spell import SpellContext, Speller
        class Fake:
            def __contains__(s, w): return w in {"привет", "мир"}
            def candidates(s, w): return {"мир"} if w == "мер" else None
            def word_usage_frequency(s, w): return 1.0
        sp = Speller.__new__(Speller); sp.lang = "ru"; sp.sp = Fake(); sp.error = ""
        self.ws.spell.speller = sp
        ed.text.setPlainText("привет мер")
        ed.update_strip()
        self.assertTrue(ed.strip.isVisible())
        ed.on_keep("мер")
        self.assertIn("мер", self.p.ignored)
        self.assertFalse(ed.strip.isVisible())

    def test_home_and_main_window(self):
        from vnstudio.ui.main_window import MainWindow
        s = Settings()
        s.projects_dir = str(self.tmp / "pr2")
        w = MainWindow(s)
        fakeqt.ANSWERS["text"] = ("Новая новелла", True)
        w.new_project()
        self.assertIsNotNone(w.ws)
        self.assertTrue(any(a.params.get("builtin") for a in w.ws.project.assets["effects"]))
        w.ws.back()
        self.assertIsNone(w.ws)
        home = w.stack.widget(0)
        home.show_projects()
        self.assertEqual(home.lst.count(), 1)
        home.open_current()
        self.assertEqual(w.ws.project.name, "Новая новелла")
        # настройки
        w.show_home()
        self.hook(lambda d: d.cb_lang.setCurrentIndex(1))
        w.open_settings()
        self.assertEqual(s.language, "en")
        from vnstudio.core.i18n import set_language
        set_language("ru")


if __name__ == "__main__":
    unittest.main(verbosity=2)

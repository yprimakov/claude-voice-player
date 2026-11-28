"""Every theme through the real player: panel, settings (and its scroll), capsule hover, minimize, restore.
Run: venv\\Scripts\\python.exe -m unittest test_player_themes"""
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("VOICED_DATA", tempfile.mkdtemp())
import player  # noqa: E402
import voiced  # noqa: E402


class FakeAudio:
    def __init__(self, wav, secs=60):
        self.secs, self.elapsed, self.playing, self.ended = secs, 0.0, False, False

    def play(self): self.playing = True
    def pause(self): self.playing = False
    position = property(lambda s: s.elapsed)
    duration = property(lambda s: s.secs)
    def close(self): self.ended = True


def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(x, y):
    a, b = sorted((lum(x), lum(y)))
    return (b + 0.05) / (a + 0.05)


class ThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = Path(tempfile.mkdtemp())
        h = voiced.History(d / "h.jsonl")
        cls.st = voiced.Settings(d / "settings.json")
        vq = voiced.VoiceQueue(h, lambda t: str(d / "x.wav"), FakeAudio, settings=cls.st)
        h.add({"id": "c1", "ts": time.time() - 60, "cwd": "C:/x/demo", "project": "demo", "session_id": "s",
               "entrypoint": "claude-desktop", "status": "spoken", "text": "Two choices are left.",
               "decisions": [{"question": "Which address?", "options": ["Studio", "Support"], "recommended": 0},
                             {"question": "Launch today?", "options": ["Yes", "Wait"], "recommended": 1}],
               "decision": {"question": "Which address?", "options": ["Studio", "Support"], "recommended": 0}})
        api = SimpleNamespace(log=lambda m: None, open_session=lambda *a, **k: "", resume_session=lambda *a, **k: False,
                              desktop_app_id=lambda *a, **k: None, type_into_desktop=lambda *a, **k: 0,
                              desktop_result={})
        cls.w = player.Widget(vq, api)

    @classmethod
    def tearDownClass(cls):
        cls.w.quit()

    def pump(self, secs=0.35):
        end = time.time() + secs
        while time.time() < end:
            self.w.root.update()
            time.sleep(0.01)

    def test_every_theme_draws_every_view(self):
        w = self.w
        for name in player.THEMES:
            with self.subTest(theme=name):
                self.st.update(theme=name)
                w._rebuild()
                self.assertEqual(player.CARD, player.THEMES[name]["CARD"])
                w._set_mode("panel")
                w._tick_once(force=True)
                self.pump()
                self.assertGreater(len(w.chips), 0)
                # the title font is the theme's (or its fallback), never Tk's default
                self.assertNotEqual(w.F["title"].actual("family"), "TkDefaultFont")
                w._toggle_settings()
                self.pump()
                self.assertEqual(w.view, "settings")
                # a short screen: the body scrolls, the panel stays inside the room
                w._room = lambda: w.p(520)
                w._layout_key = None
                w._tick_once(force=True)
                self.pump()
                self.assertGreater(w._set_max, 0)
                self.assertLessEqual(w._target_h, w.p(520))
                w._set_scroll(10 ** 6)
                self.assertEqual(w._set_off, w._set_max)
                del w._room
                w._toggle_settings()
                w._set_mode("cap")
                w._set_cap_hover(True)
                self.assertEqual(w.c.itemcget(w.btn["mini"]["g"], "state"), "normal")
                w._set_cap_hover(False)
                self.pump(0.1)
                w.minimize()
                self.pump()
                self.assertIsNotNone(w._mini)
                l, t, r, b = w._work_area(w._mini.cx, w._mini.cy)
                edge = min(w._mini.cx - l, r - w._mini.cx)
                self.assertLessEqual(edge, w._mini.ball)          # docked at a side edge
                xy = w._xy
                w.restore()
                self.pump()
                self.assertIsNone(w._mini)
                self.assertEqual(w._xy, xy)                       # back exactly where it was

    def test_hover_tint_eases_and_press_dips(self):
        w = self.w
        w._set_mode("panel")
        w._tick_once(force=True)
        self.pump()
        item = w.call_dismiss
        w.c.itemconfigure(item, fill=player.FAINT)
        w._tint(item, player.FG)
        self.assertNotEqual(w.c.itemcget(item, "fill"), player.FG)   # not a jump
        self.pump(0.3)
        self.assertEqual(w.c.itemcget(item, "fill").lower(), player.FG.lower())
        x, y = w.c.coords(item)
        w.c.configure(cursor="hand2")
        w.c.addtag_withtag("current", item)
        w._press_fx(None)
        self.assertEqual(w.c.coords(item)[1], y + 1)
        w._release_fx(None)
        self.pump(0.3)
        self.assertAlmostEqual(w.c.coords(item)[1], y, places=1)
        w.c.dtag(item, "current")
        w.c.configure(cursor="")

    def test_double_click_background_toggles(self):
        w = self.w
        w._set_mode("cap")
        self.pump(0.1)
        ev = SimpleNamespace(x_root=100, y_root=100, x=5, y=5, time=1000)
        w.c.configure(cursor="")
        w._presses = [(900, True)]                                   # the first click was on bare background
        w._drag_start(ev)
        w._double(ev)
        self.assertEqual(w.mode, "panel")
        w._drag_start(ev)
        w._drag(SimpleNamespace(x_root=140, y_root=100, x=45, y=5))  # the first click was a drag
        w._double(ev)
        self.assertEqual(w.mode, "panel")
        w._drag_start(ev)
        w.c.configure(cursor="hand2")                                # on a control
        w._double(ev)
        self.assertEqual(w.mode, "panel")
        w.c.configure(cursor="")
        w._presses = [(900, False)]                                  # first click on a nav arrow: a near miss
        w._double(ev)
        self.assertEqual(w.mode, "panel")
        w._presses = [(900, True)]
        w._double(ev)
        self.assertEqual(w.mode, "cap")
        self.assertIn("_double", w.c.tag_bind("bg", "<Double-Button-1>"))

    def test_header_never_drifts_over_the_call_row(self):
        """Toasts glide the subtitle; a relayout mid-glide must put it back, at every width and text size."""
        w = self.w
        try:
            for width in (0.9, 1.0, 1.2, 1.4):
                for size in (1.0, 1.3):
                    with self.subTest(width=width, size=size):
                        self.st.update(player_width=width, text_size=size)
                        w._rebuild()
                        w._set_mode("panel")
                        w._tick_once(force=True)
                        self.pump(0.3)
                        home = w.c.coords(w.pan_meta)[1]
                        for _ in range(12):                      # toast, then a new layout before it settles
                            w._toast("Resume command copied")
                            w.root.update()
                            w._layout_key = None
                            w._tick_once(force=True)
                        self.pump(0.4)
                        self.assertAlmostEqual(w.c.coords(w.pan_meta)[1], home, places=1)
                        meta, title = w.c.bbox(w.pan_meta), w.c.bbox(w.pan_name)
                        row = w.c.bbox("callfrom")
                        self.assertIsNotNone(row)
                        self.assertLessEqual(title[3], meta[1] + 2)  # subtitle under the title
                        self.assertLessEqual(meta[3], row[1])         # and above the YOUR CALL row
        finally:
            self.st.update(player_width=1.0, text_size=1.0)
            w._rebuild()

    def test_thread_name_shown_and_cut_before_the_project(self):
        w = self.w
        old = player.thread_title
        player.thread_title = lambda sid, cwd="": "Design System for the sample portal"
        try:
            item = {"project": "acme.app", "session_id": "s"}
            opts = w._where(item)
            self.assertEqual(opts[0], "acme.app · Design System for the sample portal")
            self.assertEqual(opts[-1], "acme.app")
            self.assertTrue(all(o.startswith("acme.app") for o in opts))
            self.assertIn("acme.app · Design System…", opts)               # cut at a word, ellipsis
            f = w.F["mono"]
            self.assertEqual(w._fit(opts, f, f.measure("acme.app · Design System…")), "acme.app · Design System…")
            self.assertEqual(w._fit(opts, f, f.measure("acme.app") + 2), "acme.app")
            w._set_mode("panel")
            w._layout_key = None
            w._tick_once(force=True)
            self.pump(0.2)
            self.assertTrue(w.c.itemcget(w.call_from, "text").startswith("demo · Design"))  # its own line
            player.thread_title = lambda sid, cwd="": "demo"                  # same as the project: hidden
            self.assertEqual(w._where({"project": "demo", "session_id": "s"}), ("demo",))
        finally:
            player.thread_title = old

    def test_project_started_session_is_never_a_call(self):
        """A reply from a "Local session (from a project)" is logged, not spoken, and never a call: its
        project thread relays what needs the user, and the link would open a session he does not drive."""
        r = {"id": "rs1", "ts": time.time() - 30, "cwd": "C:/x/agentic-os-v2", "project": "agentic-os-v2",
             "session_id": "rc-1", "entrypoint": "claude-desktop", "status": "not spoken: remote session",
             "text": "x", "decision": {"question": "Look for notes?", "options": ["A", "B"], "recommended": 0}}
        self.w.vq.history.add(r)
        self.assertFalse(any(c["id"] == "rs1" for c in self.w._collect_calls_raw(None)))

    def test_pins_order_calls_and_star(self):
        w = self.w
        now = time.time()
        rows = []
        for n, (proj, sid) in enumerate((("plain", "p1"), ("starred", "p2"), ("worked", "p3"), ("other", "p4"))):
            r = {"id": f"pc{n}", "ts": now - 30 - n, "cwd": f"C:/x/{proj}", "project": proj, "session_id": sid,
                 "entrypoint": "claude-desktop", "status": "spoken", "text": "x",
                 "decision": {"question": f"{proj}?", "options": ["A", "B"], "recommended": 0}}
            self.w.vq.history.add(r)
            rows.append(r)
        old = player.active_sessions
        player.active_sessions = lambda hours: {"p3": "worked"} if hours else {}
        try:
            self.st.update(pinned_projects=["starred"], pinned_threads=["p4"])
            order = [c["project"] for c in w._collect_calls_raw(None) if c["id"].startswith("pc")]
            self.assertEqual(order, ["other", "starred", "worked", "plain"])   # thread pin, project pin, active, rest
            self.st.update(active_hours=0)
            order = [c["project"] for c in w._collect_calls_raw(None) if c["id"].startswith("pc")]
            self.assertEqual(order, ["other", "starred", "plain", "worked"])   # boost off: newest first
            self.st.update(active_hours=2, pinned_threads=[], pinned_projects=[])
            w._set_mode("panel")
            w._tick_once(force=True)
            self.pump(0.2)
            shown = w._call()
            w._toggle_pin(shown)                                              # star it, the same call stays shown
            self.pump(0.2)
            w._tick_once(force=True)
            self.assertEqual(w._call()["id"], shown["id"])
            self.assertEqual(w.c.itemcget(w.call_pin, "text"), "★")
            self.assertIn(shown["project"], self.st.get("pinned_projects"))
            w._toggle_pin(shown)
            self.assertNotIn(shown["project"], self.st.get("pinned_projects"))
        finally:
            player.active_sessions = old
            self.st.update(pinned_projects=[], pinned_threads=[], active_hours=2)
            for r in rows:
                self.w.vq.history.update(r["id"], dismissed=True)

    def test_app_call_click_sends_the_answer(self):
        w = self.w
        it = w.vq.push_call("pc-click", "Ember OS HomeLab", "Ember OS Design", "What is CIG?", ["Client", "Venture"])
        try:
            w._reply(it, "Venture")
            a = w.vq.next_answer(0)
            self.assertEqual((a["id"], a["answer"]), ("pc-click", "Venture"))
            self.assertEqual(w.vq.history.get(it["id"])["sent_answer"], "Venture")
        finally:
            w.vq.ack_answer("pc-click")
            w.vq.push_done("pc-click")

    def test_call_nav_never_moves_and_is_a_big_target(self):
        """The arrows sit in fixed slots: the same place at 1/11 and 10/11, at least 28 px, any name length."""
        w, now = self.w, time.time()
        ids = [f"nav{n}" for n in range(11)]
        for n, i in enumerate(ids):
            w.vq.history.add({"id": i, "ts": now - 30 - n, "cwd": f"C:/x/p{n}", "project": f"p{n}" * (1 + n % 4),
                              "session_id": f"s-nav{n}", "entrypoint": "claude-desktop", "status": "spoken",
                              "text": "x", "decision": {"question": "Pick?", "options": ["a", "b"]}})
        try:
            w._set_mode("panel")
            seen = set()
            for ix in (0, 1, 9):
                w._call_ix = ix
                w._layout_key = None
                w._tick_once(force=True)
                self.pump(0.1)
                bp, bn = w.c.bbox(w._nav_bg["callprev"]), w.c.bbox(w._nav_bg["callnext"])
                self.assertGreaterEqual(bp[2] - bp[0], w.p(28) - 1)
                self.assertGreaterEqual(bn[3] - bn[1], w.p(28) - 1)
                seen.add((tuple(w.c.coords(w.call_prev)), tuple(w.c.coords(w.call_next))))
            self.assertEqual(len(seen), 1)
            band = w._call_band
            self.assertFalse(w._bare((band[0] + band[1]) / 2, ""))             # the call header never collapses
        finally:
            for i in ids:
                w.vq.history.update(i, dismissed=True)

    def test_middle_ellipsis_keeps_both_ends(self):
        f = self.w.F["mono"]
        t = "Client Portal Rebuild · Reconcile the vendor invoice grid footer totals across currencies"
        out = self.w._ellipsize_mid(t, f, f.measure(t) // 2)
        self.assertIn("…", out)
        self.assertTrue(out.startswith("Client"))
        self.assertTrue(out.endswith("currencies"))
        self.assertLessEqual(f.measure(out), f.measure(t) // 2)
        self.assertEqual(self.w._ellipsize_mid("short", f, 500), "short")

    def test_new_call_does_not_switch_away_mid_answer(self):
        """While he works through a call, a new one stays behind a NEW chip; sending or 60 s idle lets it in."""
        w, now = self.w, time.time()
        w._set_mode("panel")
        w._layout_key = None
        w._tick_once(force=True)
        self.pump(0.1)
        mine = w._call_id(w._call())
        w._touch()
        w.vq.history.add({"id": "hold-new", "ts": now, "cwd": "C:/x/other", "project": "other-proj",
                          "session_id": "s-hold", "entrypoint": "claude-desktop", "status": "spoken", "text": "x",
                          "decision": {"question": "New?", "options": ["a", "b"]}})
        try:
            w._tick_once(force=True)
            self.pump(0.1)
            self.assertEqual(w._call_id(w._call()), mine)                     # still on his call
            self.assertEqual(w._held_label(), "other-proj")
            self.assertEqual(w.c.itemcget(w.call_new, "state"), "normal")
            self.assertIn("other-proj", w.c.itemcget(w.call_new, "text"))
            w._touch_at = time.time() - w.HOLD_S - 1                          # idle: the hold runs out
            w._tick_once(force=True)
            self.pump(0.1)
            self.assertEqual(w._call_id(w._call()), "hold-new")
            self.assertEqual(w.c.itemcget(w.call_new, "state"), "hidden")
        finally:
            w.vq.history.update("hold-new", dismissed=True)
            w._release()

    def test_two_lanes_reply_never_moves_the_call(self):
        """Two lanes: the playback lane has a fixed height, so the call sits at the same y with or without a
        reply playing, and while he answers the reply still shows (it has its own lane)."""
        w = self.w
        fake = {"id": "lane-x", "ts": time.time(), "project": "other", "session_id": "s-other", "ready": True,
                "text": "A long reply summary. " * 20}
        try:
            self.st.update(layout="lanes")
            w._set_mode("panel")
            ys = []
            for show in (None, fake, {**fake, "text": "Short."}):
                w._panel(show, show, [], {"paused": False}, None, True)
                ys.append(w.c.coords(w.call_eyebrow)[1])
            self.assertEqual(len(set(ys)), 1)
            self.assertEqual(w.c.itemcget(w.lane_rule, "state"), "normal")
            self.assertTrue(w.c.itemcget(w.call_eyebrow, "text").startswith("YOUR CALLS · "))
            w._touch()                                                        # held: the reply still shows
            w._panel(fake, fake, [], {"paused": False}, None, True)
            self.assertTrue(w.c.itemcget(w.body, "text").startswith("A long reply"))
            self.assertEqual(w.c.itemcget(w.call_hold, "state"), "normal")
            self.assertEqual(w.c.coords(w.call_eyebrow)[1], ys[0])
        finally:
            w._release()
            self.st.update(layout="classic")
            w._panel(None, None, [], {"paused": False}, None, True)
        self.assertEqual(w.c.itemcget(w.lane_rule, "state"), "hidden")
        self.assertEqual(w.c.itemcget(w.call_thread, "state"), "hidden")

    def test_clamp_lines(self):
        f = self.w.F["body"]
        t = "word " * 200
        out = self.w._clamp_lines(t, f, 200, 3)
        self.assertTrue(out.endswith("…"))
        self.assertEqual(self.w._clamp_lines("two words", f, 200, 3), "two words")
        t = ("The sample guide is live and the presenter plan is ready, and I checked both on phone and desktop width. "
             "Please do a dry run on the sample seats first, since the app steps are untested, and then tell me more.")
        for width in range(250, 700, 3):  # drawn as is, never a fourth line: that one would sit on the bar
            self.assertLessEqual(self.w._clamp_lines(t, f, width, 3).count("\n"), 2, width)

    def test_lane_text_never_reaches_the_bar(self):
        w = self.w
        t = ("The sample guide is live and the presenter plan is ready, and I checked both on phone and desktop width. "
             "Please do a dry run on the sample seats first, since the app steps are untested, and then tell me more.")
        try:
            for width in range(250, 700, 3):
                w._lane_text(t, width)
                x0, y0, x1, y1 = w.c.bbox(w.body)
                self.assertLessEqual(y1 - y0, 3 * w.F["body"].metrics("linespace") + 2, width)
        finally:
            w._text(w.body, "")

    def test_thread_decisions_group_and_append(self):
        """Several replies from one thread, each with a Decisions block: one call, oldest first, a re-ask in
        place, status lines dropped, a new reply appended; answering closes every row in the group."""
        w, now = self.w, time.time()
        blk = "Done.\n\n**Decisions**\n"
        rows = [
            {"id": "g1", "ts": now - 300, "message": blk + "1. **AP-009**\n   - A. Open the PDF first. (Recommended)\n"
             "   - B. Raise it on the call.\n2. **Aerotek date in GP**\n   - A. Tell them later. (Recommended)\n"
             "   - B. Tell them now."},
            {"id": "g2", "ts": now - 200, "message": "Inbox monitor: nothing new.",
             "decision": {"question": "Ready for your review: inbox monitor polling", "options": []}},
            {"id": "g3", "ts": now - 100, "message": blk + "1. **Multi-month flag rule**\n   - A. Tell me the rule. "
             "(Recommended)\n   - B. Wait for a follow-up.\n2. AP-009\n   - A. Open the PDF and prepare a fix PR.\n"
             "   - B. Raise it on the call."},
        ]
        for r in rows:
            w.vq.history.add({**r, "cwd": "C:/x/acct", "project": "acct", "session_id": "s-grp",
                              "entrypoint": "claude-desktop", "status": "spoken", "text": "x"})
        try:
            calls = [c for c in w._collect_calls_raw(None) if c.get("session_id") == "s-grp"]
            self.assertEqual(len(calls), 1)
            c = calls[0]
            self.assertEqual(c["id"], "g1")                                    # stable while replies join
            self.assertEqual([d["question"] for d in c["decisions"]],
                             ["AP-009", "Aerotek date in GP", "Multi-month flag rule"])
            self.assertEqual(c["decisions"][0]["options"][0], "A. Open the PDF and prepare a fix PR.")  # newer wording
            self.assertEqual(c["decisions"][1]["recommended"], 0)
            self.assertTrue(c["decisions"][2]["context"].startswith("Asked "))
            w.vq.history.add({"id": "g4", "ts": now - 10, "cwd": "C:/x/acct", "project": "acct", "session_id": "s-grp",
                              "entrypoint": "claude-desktop", "status": "spoken", "text": "x",
                              "message": blk + "1. Grid footer total\n   - A. Build it now. (Recommended)\n   - B. Wait."})
            c = [c for c in w._collect_calls_raw(None) if c.get("session_id") == "s-grp"][0]
            self.assertEqual(c["id"], "g1")
            self.assertEqual(c["decisions"][-1]["question"], "Grid footer total")  # appended at the end
            w._answer(c, "1A, 2A, 3A, 4A")
            for i in ("g1", "g2", "g3", "g4"):
                self.assertEqual(w.vq.history.get(i)["answer"], "1A, 2A, 3A, 4A")
            self.assertFalse([c for c in w._collect_calls_raw(None) if c.get("session_id") == "s-grp"])
        finally:
            for i in ("g1", "g2", "g3", "g4"):
                w.vq.history.update(i, dismissed=True)

    def test_cloud_pushes_from_one_thread_group(self):
        w = self.w
        a = w.vq.push_call("cg-1", "HomeLab", "Councils", "Install the job?", ["install it", "not yet"],
                           project_id="chan_abcdef123", thread_id="cmsg_threadroot01")
        b = w.vq.push_call("cg-2", "HomeLab", "Councils", "Use my email?", ["use my email", "not yet"],
                           project_id="chan_abcdef123", thread_id="cmsg_threadroot01")
        try:
            calls = [c for c in w._collect_calls_raw(None) if c.get("thread_id") == "cmsg_threadroot01"]
            self.assertEqual(len(calls), 1)
            self.assertEqual([d["question"] for d in calls[0]["decisions"]], ["Install the job?", "Use my email?"])
            w._answer(calls[0], "x", answers=["install it", "not yet"])
            cards = [c for c in w._collect_calls_raw(None) if c.get("thread_id") == "cmsg_threadroot01"]
            self.assertEqual({c["sent_answer"] for c in cards}, {"install it", "not yet"})  # kept until DONE
            self.assertEqual({player.sent_label(c) for c in cards}, {"WAITING FOR RELAY"})
            got = {}
            for _ in range(2):
                x = w.vq.next_answer(0)
                got[x["id"]] = x["answer"]
                w.vq.ack_answer(x["id"])
            self.assertEqual(got, {"cg-1": "install it", "cg-2": "not yet"})  # one answer per pushed call
            cards = [c for c in w._collect_calls_raw(None) if c.get("thread_id") == "cmsg_threadroot01"]
            self.assertEqual({player.sent_label(c) for c in cards}, {"DELIVERED TO PROJECT"})
        finally:
            for cid in ("cg-1", "cg-2"):
                w.vq.push_done(cid)

    def test_undelivered_answers_stay_open(self):
        w, h = self.w, self.w.vq.history
        copy, opened = w._copy, []
        w._copy = opened.append  # never the real clipboard
        row = {"cwd": "C:/x/demo", "project": "demo", "entrypoint": "claude-desktop", "status": "spoken", "text": "q",
               "ts": time.time(), "decision": {"question": "Pick?", "options": ["One", "Two"], "recommended": 0}}
        try:
            h.add({**row, "id": "ps1", "session_id": "s-ps", "project_session": True, "via_thread": True})
            w._answer(next(c for c in w._collect_calls_raw(None) if c["id"] == "ps1"), "Two")
            c = next(c for c in w._collect_calls_raw(None) if c["id"] == "ps1")  # copied is not sent
            self.assertEqual((c["copied_answer"], player.sent_label(c)), ("Two", "COPIED: PASTE IT THERE"))
            h.add({**row, "id": "ty1", "session_id": "s-ty"})
            c = next(c for c in w._collect_calls_raw(None) if c["id"] == "ty1")
            w.answered.add("ty1")
            h.update("ty1", answer="Two", answered_at=time.time())
            w._typed.append((c, "Two", 6))  # pasted, but Enter did not send it
            w._typed_results()
            self.assertTrue(any(c["id"] == "ty1" for c in w._collect_calls_raw(None)))
            self.assertEqual(opened, ["Two", "Two"])
        finally:
            w._copy = copy
            for i in ("ps1", "ty1"):
                h.update(i, dismissed=True)

    def test_bundled_fonts_present_and_fallback(self):
        fonts = Path(player.__file__).with_name("fonts")
        for stem in ("VQInter", "VQInterMedium", "VQInterSemibold", "VQInterBold", "VQSpaceGroteskMedium",
                     "VQSpaceGroteskBold", "VQFrauncesSemibold", "VQFrauncesMedium", "VQFrauncesLight", "VQOutfitMedium", "VQJetBrainsMonoTracked"):
            self.assertTrue((fonts / f"{stem}.ttf").exists(), stem)
        for lic in ("Inter", "SpaceGrotesk", "Fraunces"):
            self.assertIn("Open Font License", (fonts / f"OFL-{lic}.txt").read_text(encoding="utf-8"))
        w = self.w
        fams = w._fams
        for name, sets in player.THEME_FONTS.items():
            for opts in sets:
                self.assertIn(opts[0], fams, (name, opts[0]))       # the bundled face loaded
        # a missing file falls back to the next name in the list
        saved = set(fams)
        try:
            w._fams = fams - {"VQ Inter Bold", "VQ Inter"}
            self.st.update(theme="graphite")
            w._scale_setup()
            self.assertNotIn(w.F["title"].actual("family"), ("VQ Inter Bold", "TkDefaultFont"))
        finally:
            w._fams = saved
            self.st.update(theme="ember")
            w._rebuild()

    def test_settings_sign_off_links_to_madefire(self):
        w, opened = self.w, []
        w._open_url = opened.append
        for name in ("madefire", "daylight"):
            self.st.update(theme=name)
            w._rebuild()
            w._set_mode("panel")
            w._toggle_settings()
            self.pump()
            self.assertTrue(w.c.find_withtag("madeby"))
            self.assertEqual(w.c.itemcget(w.lane_rule, "state"), "hidden")  # no Two lanes divider over the settings
            self.assertTrue(any(w.c.type(i) == "image" for i in w.c.find_withtag("madeby")))  # the wordmark
            w._toggle_settings()
        w._open_url(w.MADEFIRE_URL)
        self.assertEqual(opened[-1], "https://madefire.ai")
        self.st.update(theme="ember")
        w._rebuild()

    def test_spotlight_and_shimmer(self):
        w, st = self.w, self.st
        try:
            for theme, setting, on in (("madefire", "madefire", True), ("daylight", "madefire", True),
                                       ("ember", "madefire", False), ("ember", "all", True), ("madefire", "off", False)):
                st.update(theme=theme, spotlight=setting)
                w._rebuild()
                self.assertEqual(bool(w._fx), on, (theme, setting))
                self.assertEqual(len(w._drift_items), len(w._fx["glows"]) if on else 0)
            st.update(theme="madefire", spotlight="madefire")
            w._rebuild()
            w._set_mode("panel")
            self.pump()
            w._spot = lambda: None  # the real pointer stays out of it
            w._spot_draw((w.Wp - 3, 3))  # at a corner: the ring and the corner's curve light up
            self.assertIsNotNone(w._corner_light())
            w._spot_draw((w.Wp // 2, -40))  # outside, over the top edge: its light still reaches the top strip
            self.assertEqual([w.c.itemcget(i, "state") for i in w._spot_rim][:1], ["disabled"])
            # while speaking the whole title catches fire: no per-letter copies, the item itself changes colour
            t, n = w.pan_name, len(w.c.find_all())
            base = w._fills.get(t, player.FG)
            w._title_fire(0.6)
            self.assertNotEqual(w.c.itemcget(t, "fill"), base)
            self.assertEqual(len(w.c.find_all()), n)
            w._title_fire(None)
            self.assertEqual(w.c.itemcget(t, "fill"), base)
            w._spot_draw(None)
            self.assertIsNone(w._corner_light())
            w._slow = player.SPOT_SLOW_RUN  # frames stayed slow: the watchdog keeps the pointer light off
            w.__dict__.pop("_spot", None)
            w._spot()
            self.assertIsNone(w._spot_at)
            w.root.after_cancel(w._spot_job)
            w._spot, w._slow = (lambda: None), 0
            # ignite: each letter catches after the one before, then all rest
            ig = player.FX["madefire"]["ig"]
            self.assertIsNone(player.ignite(0, 0.3, "#ffffff", ig))
            self.assertIsNotNone(player.ignite(0, 0.6, "#ffffff", ig))
            self.assertIsNone(player.ignite(8, 0.6, "#ffffff", ig))
            self.assertIsNone(player.ignite(0, 3.0, "#ffffff", ig))
            before = [w.c.coords(i) for i in w._drift_items]
            w._drift_place(0.0)
            first = [w.c.coords(i) for i in w._drift_items]
            w._drift_place(20.0)
            self.assertNotEqual(first, [w.c.coords(i) for i in w._drift_items])
            st.update(reduce_motion=True)  # drifting stops, the pointer light stays
            w._drift_job = None
            w._drift()
            self.assertIsNone(w._drift_job)
            self.assertTrue(w._fx)
            self.assertEqual(len(before), 4)
        finally:
            w.__dict__.pop("_spot", None)
            w._spot_job = None
            st.update(theme="ember", spotlight="madefire", reduce_motion=False)
            w._rebuild()

    def test_settings_scroll_stays_fast(self):
        """The Settings body scrolled to the bottom and back many times: each step and its repaint fit a frame
        budget, in the light and the dark MadeFire theme, with the pointer light off and on."""
        import statistics
        w = self.w

        def restore():
            w.__dict__.pop("_room", None)
            if w.view == "settings":
                w._toggle_settings()
            self.st.update(theme="ember", spotlight="madefire")
            w._rebuild()
        self.addCleanup(restore)
        for theme in ("madefire", "daylight"):
            for spot in ("off", "all"):
                with self.subTest(theme=theme, spotlight=spot):
                    self.st.update(theme=theme, spotlight=spot)
                    w._rebuild()
                    w._set_mode("panel")
                    w._toggle_settings()
                    w._room = lambda: w.p(520)
                    w._layout_key = None
                    w._tick_once(force=True)
                    self.pump(0.2)
                    self.assertGreater(w._set_max, 0)
                    steps, t_all = [], time.perf_counter()
                    for n in range(60):
                        t0 = time.perf_counter()
                        w._set_scroll(w._set_off + (w.p(48) if (n // 15) % 2 == 0 else -w.p(48)))
                        w.root.update()
                        steps.append((time.perf_counter() - t0) * 1000)
                    total = time.perf_counter() - t_all
                    self.assertLess(statistics.median(steps), 40, steps)
                    self.assertLess(max(steps), 400, steps)
                    self.assertLess(total, 6.0)
                    del w._room
                    w._toggle_settings()

    def test_long_setting_hint_wraps_without_overlap(self):
        w = self.w
        self.st.update(theme="madefire", spotlight="madefire", player_width=0.85)
        w._rebuild()
        w._set_mode("panel")
        w._toggle_settings()
        self.pump(0.2)
        c = w.c

        def box(text):
            return next(c.bbox(i) for i in c.find_withtag("set") if c.type(i) == "text" and c.itemcget(i, "text") == text)
        hint = box(next(c.itemcget(i, "text") for i in c.find_withtag("set")
                        if c.type(i) == "text" and c.itemcget(i, "text").startswith("A light follows")))
        self.assertLessEqual(hint[3], box("Reduce motion")[1])
        w._toggle_settings()
        self.st.update(theme="ember", spotlight="all", player_width=1.0)
        w._rebuild()

    def test_hover_never_changes_the_hovered_item(self):
        """A hover handler that changes the item's font or coords moves its hit area, and Tk's re-pick
        can then flip Enter/Leave forever (the Settings freeze of 2026-11-27). Enter/Leave keep shape."""
        w = self.w
        w._set_mode("panel")
        w._toggle_settings()
        self.pump(0.2)
        c = w.c
        items = [i for i in c.find_withtag("set") if c.type(i) == "text"]
        before = {i: (c.itemcget(i, "font"), c.itemcget(i, "text"), c.coords(i)) for i in items}
        link = next(i for i in c.find_withtag("madeby") if c.type(i) == "text")
        bb = c.bbox(link)
        n = [0]
        def enter(e):
            n[0] += 1
            if n[0] > 50:  # a loop: break it so the test fails instead of hanging
                c.tag_unbind("madeby", "<Enter>")
                c.tag_unbind("madeby", "<Leave>")
        c.tag_bind("madeby", "<Enter>", enter, add="+")
        for y in range(bb[1], bb[3] + 1):  # every row, the underline row included
            c.event_generate("<Motion>", x=(bb[0] + bb[2]) // 2, y=y)
            c.itemconfigure(link, fill=c.itemcget(link, "fill"))  # forces a re-pick, like a scroll does
            self.pump(0.02)
        self.assertLess(n[0], 10, "Enter/Leave loop on the madefire.ai link")
        after = {i: (c.itemcget(i, "font"), c.itemcget(i, "text"), c.coords(i)) for i in items}
        self.assertEqual(before[link], after[link])
        self.assertEqual(c.bbox(link), bb)
        w._toggle_settings()

    def test_both_paper_looks_draw(self):
        """Look B is parked (SHEET_LOOK picks A) but must still draw, for both MadeFire themes."""
        for name in ("madefire", "daylight"):
            for look, sh in player.SHEET_LOOKS[name].items():
                with self.subTest(theme=name, look=look):
                    old = player.SHEETS[name]
                    player.SHEETS[name] = sh
                    try:
                        im = player.Art(1.0).sheet(name, 320, 480)
                    finally:
                        player.SHEETS[name] = old
                    self.assertIsNotNone(im)

    def test_spot_frame_under_budget(self):
        """One pointer-light frame (the main-thread work for a pointer move) fits the 8 ms target."""
        import statistics
        w = self.w
        self.st.update(theme="madefire", spotlight="madefire")
        w._rebuild()
        w._set_mode("panel")
        self.pump(0.2)
        self.assertTrue(w._fx)
        self.addCleanup(w._spot_draw, None)
        times = []
        for n in range(60):
            x, y = 6 * n % w.Wp, 17 * n % w.h  # a sweep across the card
            at = (x - x % 3, y - y % 3)  # the 3 px steps _spot uses
            t0 = time.perf_counter()
            w._spot_draw(at)
            times.append((time.perf_counter() - t0) * 1000)
        self.assertLess(statistics.median(times), 8, times)  # measured about 2 ms

    def test_hang_watch_writes_the_stuck_stack(self):
        w = self.w
        before = set(voiced.data_dir().glob("hang-*.txt"))
        old = player.HANG_S
        player.HANG_S = 1.0
        try:
            w._hang_watch()
            new, t0 = set(), time.monotonic()
            while not new and time.monotonic() - t0 < 8:  # the UI thread stays blocked: no heartbeat
                time.sleep(0.2)
                new = set(voiced.data_dir().glob("hang-*.txt")) - before
            time.sleep(0.3)  # let the dump finish
            self.assertEqual(len(new), 1)
            text = next(iter(new)).read_text(encoding="utf-8")
            self.assertTrue(text.startswith("player UI thread stuck"), text[:80])  # header before the stacks
            self.assertIn("test_hang_watch_writes_the_stuck_stack", text)  # the stuck UI thread's own frame
        finally:
            w._hang_stop.set()
            player.HANG_S = old

    def test_paper_sheet(self):
        w, st = self.w, self.st
        try:
            st.update(theme="daylight")
            w._rebuild()
            for mode in ("cap", "panel"):
                w._set_mode(mode)
                self.pump()
                w._set_height(w._target_h)
                self.assertEqual(w._sheet_pil.size, (w.Wp, w._target_h))  # the linen covers the whole card
                self.assertEqual(w.c.itemcget(w.sheet, "state"), "disabled")
            self.assertGreater(len(w._sheet_pil.crop((100, 100, 160, 160)).getcolors(4000)), 8)  # it has a texture
            w._set_mode("panel")
            self.pump()
            w._spot = lambda: None
            w._spot_draw((150, 10))  # only the edge on the pointer's half follows it: the other keeps its image
            subs = list(w._foil_sub)
            w._spot_draw((260, 12))
            self.assertNotEqual(w._foil_sub[0], subs[0])
            self.assertEqual(w._foil_sub[1:], subs[1:])
            w._spot_draw(None)
            w.__dict__.pop("_spot", None)
            row = w.art.foil(400, 120)  # the copper is brightest at the pointer
            lum = [sum(row.getpixel((x, 0))) for x in range(400)]
            self.assertLess(abs(lum.index(max(lum)) - 120), 6)
            flat = w.art.sheet("daylight", 60, 60)
            mean = [sum(flat.getpixel((x, y))[k] for x in range(60) for y in range(60)) / 3600 for k in range(3)]
            for got, want in zip(mean, player._rgb(player.THEMES["daylight"]["CARD"])):
                self.assertLess(abs(got - want), 8)  # CARD stays the sheet's mean: masks and mixes use it
        finally:
            st.update(theme="ember")
            w._rebuild()

    def test_theme_colours_are_readable(self):
        for name, t in player.THEMES.items():
            with self.subTest(theme=name):
                for fg in ("FG", "BODY", "MUTED", "FAINT", "EMBER"):
                    self.assertGreaterEqual(ratio(t[fg], t["CARD"]), 4.5, fg)
                for end in t["ACC"] + t["ACC_HI"]:
                    self.assertGreaterEqual(ratio(t["ACC_INK"], end), 4.5)
                    self.assertGreaterEqual(ratio(t["SW_KNOB"], end), 1.3)  # the switch knob stands out
                if t.get("CHIP"):
                    self.assertGreaterEqual(ratio(t["CHIP"][1], t["CHIP"][0]), 4.5)
                self.assertEqual(len(player.THEME_FONTS[name]), 5)


if __name__ == "__main__":
    unittest.main()

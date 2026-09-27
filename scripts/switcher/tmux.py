"""Safe tmux client and server adapter with readback and stable IDs."""
import subprocess
from scripts.switcher.model import Window, Pane, SessionGroup


def _stable_key(identity: str) -> str:
    """Dependency-free stable hex key for a client identity string."""
    key = 0
    for byte in identity.encode("utf-8"):
        key = ((key * 131) ^ byte) & 0xFFFFFFFFFFFFFFFF
    return "%016x" % key


class TmuxAdapter:
    def __init__(self, socket_path=None, client_target=None):
        self.socket_path = socket_path
        self.client_target = client_target

    def _cmd(self, args):
        cmd = ["tmux"]
        if self.socket_path:
            cmd.extend(["-S", self.socket_path])
        cmd.extend(args)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode, proc.stdout, proc.stderr

    def _return_option(self):
        """Server-scoped option keyed by the explicit client instance, not reusable TTY alone."""
        if not self.client_target:
            raise RuntimeError("Explicit tmux client required for switch history")
        fmt = "#{client_tty}\t#{client_pid}\t#{client_created}"
        code, out, err = self._cmd(["display-message", "-c", self.client_target, "-p", fmt])
        parts = out.strip().split("\t")
        if code != 0 or len(parts) != 3 or not all(parts):
            raise RuntimeError(err.strip() or "Client identity unavailable")
        return "@window_switch_return_" + _stable_key(out.strip())

    def get_client_size(self):
        """Return (width, height) of the target client, or (0, 0) if unavailable."""
        if not self.client_target:
            return (0, 0)
        code, out, _ = self._cmd([
            "display-message", "-c", self.client_target, "-p",
            "#{client_width}\t#{client_height}"
        ])
        if code != 0:
            return (0, 0)
        parts = out.strip().split("\t")
        if len(parts) != 2:
            return (0, 0)
        try:
            return (int(parts[0]), int(parts[1]))
        except ValueError:
            return (0, 0)

    def get_return_window_id(self):
        code, out, err = self._cmd(["show-options", "-gqv", self._return_option()])
        if code != 0:
            raise RuntimeError(err.strip() or "Cannot read return window")
        return out.strip() or None

    def set_return_window_id(self, source_window_id):
        option = self._return_option()
        code, _, err = self._cmd(["set-option", "-g", option, source_window_id])
        if code != 0:
            raise RuntimeError(err.strip() or "Cannot save return window")
        if self.get_return_window_id() != source_window_id:
            raise RuntimeError("Return window readback mismatch")

    def get_source_window_id(self):
        """Get source window stable ID #{window_id} for the current client."""
        args = ["display-message"]
        if self.client_target:
            args.extend(["-c", self.client_target])
        args.extend(["-p", "#{window_id}"])
        code, out, err = self._cmd(args)
        if code != 0 or not out.strip():
            raise RuntimeError(err.strip() or "Cannot identify source window")
        return out.strip()

    def get_snapshot(self):
        """
        Query tmux for all sessions, windows, and panes.
        Returns (groups, source_window_id).
        """
        src_wid = self.get_source_window_id()

        # Query windows format
        # session_id, session_name, window_id, window_index, window_name, window_active, window_last_flag
        w_format = "#{session_id}\t#{session_name}\t#{window_id}\t#{window_index}\t#{window_name}\t#{window_active}\t#{window_last_flag}\t#{pane_id}\t#{pane_current_command}\t#{pane_current_path}"
        code, out, err = self._cmd(["list-windows", "-a", "-F", w_format])
        if code != 0:
            raise RuntimeError(err.strip() or "Cannot list windows")
        
        # Query panes format
        # window_id, pane_id, pane_index, pane_title, pane_current_command, pane_current_path, pane_pid, pane_active, pane_width, pane_height, pane_left, pane_top
        p_format = "#{window_id}\t#{pane_id}\t#{pane_index}\t#{pane_title}\t#{pane_current_command}\t#{pane_current_path}\t#{pane_pid}\t#{pane_active}\t#{pane_width}\t#{pane_height}\t#{pane_left}\t#{pane_top}"
        code, p_out, err = self._cmd(["list-panes", "-a", "-F", p_format])
        if code != 0:
            raise RuntimeError(err.strip() or "Cannot list panes")

        panes_by_win: Dict[str, List[Pane]] = {}
        for line in p_out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 12:
                wid = parts[0]
                p = Pane(
                    pane_id=parts[1],
                    pane_index=int(parts[2]) if parts[2].isdigit() else 0,
                    pane_title=parts[3],
                    pane_current_command=parts[4],
                    pane_current_path=parts[5],
                    pane_pid=int(parts[6]) if parts[6].isdigit() else 0,
                    pane_active=(parts[7] == "1"),
                    pane_width=int(parts[8]) if parts[8].isdigit() else 80,
                    pane_height=int(parts[9]) if parts[9].isdigit() else 24,
                    pane_left=int(parts[10]) if parts[10].isdigit() else 0,
                    pane_top=int(parts[11]) if parts[11].isdigit() else 0
                )
                panes_by_win.setdefault(wid, []).append(p)

        groups_map: Dict[str, SessionGroup] = {}
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 10:
                sid, sname, wid, widx_s, wname, wact, wlast, pid, pcmd, ppath = parts[:10]
                widx = int(widx_s) if widx_s.isdigit() else 0
                is_cur = (wid == src_wid)

                win = Window(
                    session_name=sname,
                    session_id=sid,
                    session_alias="1", # will be set by AppState
                    window_id=wid,
                    window_index=widx,
                    window_name=wname,
                    is_active=(wact == "1"),
                    is_last=(wlast == "1"),
                    is_current=is_cur,
                    active_pane_id=pid,
                    active_pane_command=pcmd,
                    active_pane_path=ppath,
                    panes=panes_by_win.get(wid, [])
                )
                if sname not in groups_map:
                    groups_map[sname] = SessionGroup(session_name=sname, session_id=sid, session_alias="1", windows=[])
                groups_map[sname].windows.append(win)

        return list(groups_map.values()), src_wid

    def capture_pane(self, pane_id, num_lines: int = 50):
        """Capture visible pane content read-only without modifying pane state."""
        code, out, _ = self._cmd(["capture-pane", "-p", "-t", pane_id])
        if code == 0:
            return out.splitlines()
        return []

    def switch_client(self, target_window_id):
        """Switch client to target window using stable window ID #{window_id}."""
        args = ["switch-client"]
        if self.client_target:
            args.extend(["-c", self.client_target])
        args.extend(["-t", target_window_id])
        code, out, err = self._cmd(args)
        if code != 0:
            return False, err.strip()
        try:
            actual = self.get_source_window_id()
        except RuntimeError as exc:
            return False, str(exc)
        if actual != target_window_id:
            return False, f"Switch readback mismatch: {actual}"
        return True, ""

    def kill_window(self, target_window_id, source_window_id):
        """Kill window safely using stable window ID. Never kills source window."""
        if target_window_id == source_window_id:
            return False, "Deleting source window is strictly forbidden"
        try:
            if self.get_source_window_id() != source_window_id:
                return False, "Source window changed; deletion cancelled"
            groups, _ = self.get_snapshot()
        except RuntimeError as exc:
            return False, str(exc)
        matches = [w for g in groups for w in g.windows if w.window_id == target_window_id]
        if len(matches) != 1:
            return False, "Target window missing or linked; deletion cancelled"
        code, out, err = self._cmd(["kill-window", "-t", target_window_id])
        if code != 0:
            return False, err.strip()
        code, remaining, err = self._cmd(["list-windows", "-a", "-F", "#{window_id}"])
        if code != 0 or target_window_id in remaining.splitlines():
            return False, err.strip() or "Deletion readback failed"
        return True, ""

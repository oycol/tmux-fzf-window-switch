"""Safe tmux client and server adapter with readback and stable IDs."""
import subprocess
from typing import List, Dict, Tuple, Optional
from scripts.switcher.model import Window, Pane, SessionGroup

class TmuxAdapter:
    def __init__(self, socket_path: Optional[str] = None, client_target: Optional[str] = None):
        self.socket_path = socket_path
        self.client_target = client_target

    def _cmd(self, args: List[str]) -> Tuple[int, str, str]:
        cmd = ["tmux"]
        if self.socket_path:
            cmd.extend(["-S", self.socket_path])
        cmd.extend(args)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode, proc.stdout, proc.stderr

    def get_source_window_id(self) -> str:
        """Get source window stable ID #{window_id} for the current client."""
        args = ["display-message"]
        if self.client_target:
            args.extend(["-c", self.client_target])
        args.extend(["-p", "#{window_id}"])
        code, out, err = self._cmd(args)
        return out.strip()

    def get_snapshot(self) -> Tuple[List[SessionGroup], str]:
        """
        Query tmux for all sessions, windows, and panes.
        Returns (groups, source_window_id).
        """
        src_wid = self.get_source_window_id()

        # Query windows format
        # session_id, session_name, window_id, window_index, window_name, window_active, window_last_flag
        w_format = "#{session_id}\t#{session_name}\t#{window_id}\t#{window_index}\t#{window_name}\t#{window_active}\t#{window_last_flag}\t#{pane_id}\t#{pane_current_command}\t#{pane_current_path}"
        code, out, _ = self._cmd(["list-windows", "-a", "-F", w_format])
        
        # Query panes format
        # window_id, pane_id, pane_index, pane_title, pane_current_command, pane_current_path, pane_pid, pane_active, pane_width, pane_height, pane_left, pane_top
        p_format = "#{window_id}\t#{pane_id}\t#{pane_index}\t#{pane_title}\t#{pane_current_command}\t#{pane_current_path}\t#{pane_pid}\t#{pane_active}\t#{pane_width}\t#{pane_height}\t#{pane_left}\t#{pane_top}"
        _, p_out, _ = self._cmd(["list-panes", "-a", "-F", p_format])

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

    def capture_pane(self, pane_id: str, num_lines: int = 50) -> List[str]:
        """Capture visible pane content read-only without modifying pane state."""
        code, out, _ = self._cmd(["capture-pane", "-p", "-t", pane_id, "-S", f"-{num_lines}"])
        if code == 0:
            return out.splitlines()
        return []

    def switch_client(self, target_window_id: str) -> Tuple[bool, str]:
        """Switch client to target window using stable window ID #{window_id}."""
        args = ["switch-client"]
        if self.client_target:
            args.extend(["-c", self.client_target])
        args.extend(["-t", target_window_id])
        code, out, err = self._cmd(args)
        return (code == 0, err.strip() if code != 0 else "")

    def kill_window(self, target_window_id: str, source_window_id: str) -> Tuple[bool, str]:
        """Kill window safely using stable window ID. Never kills source window."""
        if target_window_id == source_window_id:
            return False, "Deleting source window is strictly forbidden"
        code, out, err = self._cmd(["kill-window", "-t", target_window_id])
        return (code == 0, err.strip() if code != 0 else "")

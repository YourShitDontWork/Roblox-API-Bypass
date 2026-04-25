import os
import subprocess
import random
import winreg
import time
import urllib.request
import urllib.error
import shutil
import threading
from pathlib import Path
import customtkinter as ctk
from tkinter import messagebox
import sqlite3
from pathlib import Path

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

REGISTRY_BASE = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}"
VIRTUAL_MAC_PREFIXES = ("08:00:27", "0A:00:27", "00:50:56", "00:0C:29", "00:05:69", "00:1C:14", "00:15:5D")
SKIP_KEYWORDS = ("virtual", "vmware", "hyper-v", "loopback", "bluetooth", "miniport", "tunnel", "vpn", "vbox")

def clear_browser_cookies():
    local = os.environ.get('LOCALAPPDATA', '')
    appdata = os.environ.get('APPDATA', '')

    confirm = messagebox.askyesno(
        "Close Browsers?",
        "To clear cookies, open browsers need to be closed.\n\nClose all browsers now?"
    )
    if confirm:
        browsers_to_kill = [
            "chrome.exe", "msedge.exe", "brave.exe",
            "opera.exe", "vivaldi.exe", "firefox.exe"
        ]
        for browser in browsers_to_kill:
            subprocess.run(
                ["taskkill", "/F", "/IM", browser],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        time.sleep(1.5)

    cookie_paths = [
        Path(local) / "Google/Chrome/User Data/Default/Network/Cookies",
        Path(local) / "Google/Chrome/User Data/Default/Cookies",
        Path(local) / "Microsoft/Edge/User Data/Default/Network/Cookies",
        Path(local) / "Microsoft/Edge/User Data/Default/Cookies",
        Path(local) / "BraveSoftware/Brave-Browser/User Data/Default/Network/Cookies",
        Path(local) / "BraveSoftware/Brave-Browser/User Data/Default/Cookies",
        Path(appdata) / "Opera Software/Opera Stable/Network/Cookies",
        Path(appdata) / "Opera Software/Opera Stable/Cookies",
        Path(appdata) / "Opera Software/Opera GX Stable/Network/Cookies",
        Path(appdata) / "Opera Software/Opera GX Stable/Cookies",
        Path(local) / "Vivaldi/User Data/Default/Network/Cookies",
        Path(local) / "Vivaldi/User Data/Default/Cookies",
    ]

    for path in cookie_paths:
        try:
            if path.exists():
                conn = sqlite3.connect(str(path))
                conn.execute("DELETE FROM cookies WHERE host_key LIKE '%roblox.com%'")
                conn.commit()
                conn.close()
        except Exception:
            pass

    firefox_profiles = Path(appdata) / "Mozilla/Firefox/Profiles"
    if firefox_profiles.exists():
        for profile in firefox_profiles.iterdir():
            cookies_db = profile / "cookies.sqlite"
            if cookies_db.exists():
                try:
                    conn = sqlite3.connect(str(cookies_db))
                    conn.execute("DELETE FROM moz_cookies WHERE host LIKE '%roblox.com%'")
                    conn.commit()
                    conn.close()
                except Exception:
                    pass

    roblox_cookie_paths = [
        Path(local) / "Roblox/LocalStorage",
        Path(local) / "Roblox/cookies",
    ]
    for path in roblox_cookie_paths:
        try:
            if path.exists():
                shutil.rmtree(path)
        except Exception:
            pass


def wait_for_reconnection(status_callback):
    attempt = 0
    while True:
        try:
            urllib.request.urlopen("https://www.google.com", timeout=3)
            return
        except Exception:
            attempt += 1
            status_callback(f"Waiting for reconnection... (attempt {attempt})", is_working=True)
            time.sleep(2)


class NetworkManager:
    @staticmethod
    def get_real_adapter():
        output = subprocess.run("getmac /v /fo csv /nh", shell=True, capture_output=True, text=True).stdout.strip()

        for line in output.splitlines():
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) < 4:
                continue

            name, _, mac, transport = parts
            mac = mac.replace("-", ":")

            if mac == "N/A" or "Media disconnected" in transport:
                continue

            if any(k in name.lower() for k in SKIP_KEYWORDS):
                continue
            if mac[:8].upper() in VIRTUAL_MAC_PREFIXES:
                continue

            return name, mac
        return None, None

    @staticmethod
    def generate_mac():
        mac = [random.randint(0x00, 0xFF) for _ in range(6)]
        mac[0] = (mac[0] & 0xFC) | 0x02
        return ":".join(f"{b:02X}" for b in mac)

    @staticmethod
    def set_registry_mac(adapter_name, new_mac):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REGISTRY_BASE) as base:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(base, i)
                        subkey_path = rf"{REGISTRY_BASE}\{subkey_name}"

                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey_path, 0, winreg.KEY_ALL_ACCESS) as subkey:
                            name, _ = winreg.QueryValueEx(subkey, "DriverDesc")

                            if adapter_name.lower() in name.lower():
                                clean_mac = new_mac.replace(":", "").replace("-", "")
                                winreg.SetValueEx(subkey, "NetworkAddress", 0, winreg.REG_SZ, clean_mac)
                                return True
                    except FileNotFoundError:
                        pass
                    except OSError:
                        break
                    i += 1
        except PermissionError:
            raise PermissionError("Registry access denied. Script must be run as Administrator.")
        return False

    @staticmethod
    def restart_adapter(name):
        subprocess.run(f'netsh interface set interface "{name}" disable', shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(1.5)
        subprocess.run(f'netsh interface set interface "{name}" enable', shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)


class SpooferApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MAC Spoofer For Roblox")
        self.geometry("500x480")
        self.resizable(False, False)

        self.net_manager = NetworkManager()
        self.adapter_name, self.current_mac = self.net_manager.get_real_adapter()
        self.target_mac = self.net_manager.generate_mac()

        self._build_ui()

    def _build_ui(self):
        self.header = ctk.CTkLabel(self, text="MAC Spoofer For Roblox", font=ctk.CTkFont(size=20, weight="bold"))
        self.header.pack(pady=(20, 5))

        self.sub_header = ctk.CTkLabel(self, text="Deletes and Reinstalls Roblox and changes your MAC Address", text_color="gray")
        self.sub_header.pack(pady=(0, 20))

        self.info_frame = ctk.CTkFrame(self)
        self.info_frame.pack(padx=20, pady=10, fill="x")

        self._add_info_row("Adapter:", self.adapter_name or "Not Found")
        self._add_info_row("Current MAC:", self.current_mac or "N/A")
        self._add_info_row("Target MAC:", self.target_mac, is_highlight=True)

        self.status_label = ctk.CTkLabel(self, text="Ready", font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=(20, 5))

        self.progress = ctk.CTkProgressBar(self, mode="indeterminate")
        self.progress.pack(padx=40, pady=10, fill="x")
        self.progress.set(0)

        self.run_btn = ctk.CTkButton(
            self,
            text="Start Bypass",
            height=40,
            command=self.start_worker_thread
        )
        self.run_btn.pack(pady=20)

    def _add_info_row(self, label_text, value_text, is_highlight=False):
        row = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(row, text=label_text, text_color="gray").pack(side="left")

        val_color = "#3b8ed0" if is_highlight else "white"
        ctk.CTkLabel(row, text=value_text, text_color=val_color, font=ctk.CTkFont(weight="bold")).pack(side="right")

    def update_ui_state(self, message, is_working=False):
        self.status_label.configure(text=message)
        if is_working:
            self.run_btn.configure(state="disabled")
            self.progress.start()
        else:
            self.run_btn.configure(state="normal")
            self.progress.stop()
            self.progress.set(0)

    def start_worker_thread(self):
        if not self.adapter_name:
            messagebox.showerror("Error", "No valid network adapter found.")
            return

        threading.Thread(target=self._execution_sequence, daemon=True).start()

    def _execution_sequence(self):
        try:
            self.update_ui_state("Clearing session cookies...", is_working=True)
            clear_browser_cookies()
            time.sleep(1)

            self.update_ui_state("Applying new MAC address...", is_working=True)
            self.net_manager.set_registry_mac(self.adapter_name, self.target_mac)

            self.update_ui_state("Restarting network adapter...", is_working=True)
            self.net_manager.restart_adapter(self.adapter_name)

            wait_for_reconnection(self.update_ui_state)

            self.update_ui_state("Purging target application data...", is_working=True)
            app_path = Path(os.environ['LOCALAPPDATA']) / 'Roblox'
            if app_path.exists():
                shutil.rmtree(app_path)

            self.update_ui_state("Downloading fresh installer...", is_working=True)
            installer_url = "https://www.roblox.com/download/client"
            temp_path = Path(os.environ['TEMP']) / 'RobloxPlayerInstaller.exe'

            def progress(block_num, block_size, total_size):
                if total_size > 0:
                    pct = min(block_num * block_size * 100 / total_size, 100)
                    self.update_ui_state(f"Downloading... {pct:.1f}%", is_working=True)

            urllib.request.urlretrieve(installer_url, temp_path, reporthook=progress)

            self.update_ui_state("Running installer...", is_working=True)
            subprocess.run([str(temp_path)], shell=True)

            try:
                os.remove(temp_path)
            except Exception:
                pass

            self.update_ui_state("Opening Roblox...", is_working=True)
            import webbrowser
            webbrowser.open("https://www.roblox.com")

            self.update_ui_state("Sequence complete.", is_working=False)
            messagebox.showinfo("Success", f"Sequence finished.\nNew MAC: {self.target_mac}")

        except Exception as e:
            self.update_ui_state("Sequence encountered an error.", is_working=False)
            messagebox.showerror("Error", f"An unexpected error occurred:\n{str(e)}")

        self.adapter_name, self.current_mac = self.net_manager.get_real_adapter()
        self.target_mac = self.net_manager.generate_mac()


if __name__ == "__main__":
    app = SpooferApp()
    app.mainloop()

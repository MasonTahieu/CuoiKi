"""Local credential form. Network work runs outside the GUI thread."""
import queue
import re
import threading
import tkinter as tk
from tkinter import ttk

from dotenv import dotenv_values
from src.config import PROJECT_ROOT
from src.neo_api.login import obtain_token, save_token
from src.neo_api.rest import AuthError


def main():
    root = tk.Tk()
    root.title("Đăng nhập NEO — lấy token cho dự án")
    root.geometry("580x440")
    root.minsize(580,440)
    panel = ttk.Frame(root, padding=24)
    panel.pack(fill="both",expand=True)
    ttk.Label(panel,text="Kết nối NEO Invest",font=("Segoe UI",18,"bold")).pack(anchor="w")
    ttk.Label(panel,text="Thông tin được gửi trực tiếp đến máy chủ xác thực VPBS.").pack(anchor="w",pady=(4,16))
    username, password = tk.StringVar(), tk.StringVar()
    path = PROJECT_ROOT / ".env"
    values = dotenv_values(path,interpolate=False) if path.exists() else {}
    device = values.get("NEO_DEVICE_ID") or "vn30-screener"
    ttk.Label(panel,text="Số lưu ký / tên đăng nhập NEO Invest").pack(anchor="w")
    user_entry = ttk.Entry(panel,textvariable=username,font=("Segoe UI",12))
    user_entry.pack(fill="x",pady=(4,12))
    ttk.Label(panel,text="Mật khẩu NEO Invest").pack(anchor="w")
    pass_entry = ttk.Entry(panel,textvariable=password,show="*",font=("Segoe UI",12))
    pass_entry.pack(fill="x",pady=(4,6))
    visible = tk.BooleanVar(value=False)
    ttk.Checkbutton(panel,text="Hiện mật khẩu",variable=visible,
        command=lambda:pass_entry.configure(show="" if visible.get() else "*")).pack(anchor="w")
    status = tk.StringVar(value="Nhập tài khoản hiện có của VPBankS rồi bấm Đăng nhập.")
    messages = queue.Queue()
    busy = [False]

    def worker(user,secret):
        try:
            token, expires = obtain_token(user,secret)
            save_token(path,token,device,expires)
            messages.put((True,"Đã lấy và lưu token vào .env. Bạn có thể đóng cửa sổ và báo đăng nhập thành công."))
        except AuthError as error:
            messages.put((False,str(error)))
        except OSError:
            messages.put((False,"Chưa lưu được token vào .env. Kiểm tra quyền ghi thư mục dự án."))
        except Exception:
            # Do not echo request objects, response bodies or unknown errors containing credentials.
            messages.put((False,"Có lỗi khi xử lý đăng nhập. Chưa xác nhận lưu token thành công."))

    def submit(event=None):
        if busy[0]:
            return
        user, secret = username.get().strip(),password.get()
        if not user or not secret:
            status.set("Bạn cần điền số lưu ký và mật khẩu.")
            return
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}",device):
            status.set("Device ID trong .env không hợp lệ; cần kiểm tra cấu hình.")
            return
        busy[0] = True
        button.configure(state="disabled")
        user_entry.configure(state="disabled")
        pass_entry.configure(state="disabled")
        visible.set(False)
        pass_entry.configure(show="*")
        status.set("Đang đăng nhập… Vui lòng chờ phản hồi từ VPBS.")
        threading.Thread(target=worker,args=(user,secret),daemon=True).start()

    def poll():
        try:
            success, message = messages.get_nowait()
        except queue.Empty:
            root.after(100,poll)
            return
        busy[0] = False
        password.set("")
        status.set(message)
        user_entry.configure(state="normal")
        pass_entry.configure(state="normal")
        button.configure(state="disabled" if success else "normal")
        root.after(100,poll)

    button = ttk.Button(panel,text="Đăng nhập và lưu token",command=submit)
    button.pack(fill="x",pady=(16,12))
    ttk.Label(panel,textvariable=status,wraplength=520).pack(anchor="w")
    ttk.Label(panel,text="Mật khẩu không được lưu. Token chỉ lưu trong .env của dự án.",
        wraplength=520).pack(anchor="w",pady=(12,0))
    root.bind("<Return>",submit)
    user_entry.focus_set()
    root.after(100,poll)
    root.mainloop()


if __name__ == "__main__":
    main()

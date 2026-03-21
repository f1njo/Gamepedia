import os
import json
import hashlib
import io
import re
import sys
import tkinter as tk
from tkinter import messagebox
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from PIL import Image, ImageDraw, ImageTk
from db import (
    get_connection,
    fetch_all_games,
    fetch_user_by_username,
    create_user,
    delete_duplicate_games_by_title,
    add_favorite,
    remove_favorite,
    is_favorite,
    fetch_user_favorite_games,
)

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = APP_DIR


def app_path(*parts):
    return os.path.join(APP_DIR, *parts)


def bundle_path(*parts):
    return os.path.join(BUNDLE_DIR, *parts)


USERS_FILE = app_path("users.json")
PROPOSALS_FILE = app_path("proposals.txt")
GAME_FIELDS = [
    ("Название", "название"),
    ("Год", "год"),
    ("Жанр", "жанр"),
    ("Разработчик", "разработчик"),
    ("Платформы", "платформы"),
    ("Рейтинг", "рейтинг"),
    ("Описание", "описание"),
]
BANNER_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
STEAM_SEARCH_URL = "https://store.steampowered.com/api/storesearch/"
HTTP_HEADERS = {
    "User-Agent": "Gamepedia/1.0 (+https://steamcommunity.com/)",
}


def normalize_banner_name(title):
    normalized = (title or "").strip()
    normalized = re.sub(r'[<>:"/\\\\|?*]', "_", normalized)
    return normalized.strip(". ") or "banner"


def build_banner_path(title):
    return app_path("banners", f"{normalize_banner_name(title)}.jpg")


def get_existing_banner_path(title):
    raw_title = (title or "").strip()
    if not raw_title:
        return None

    candidates = []
    for variant in (raw_title, normalize_banner_name(raw_title)):
        for ext in BANNER_EXTENSIONS:
            candidates.append(app_path("banners", f"{variant}{ext}"))
            candidates.append(bundle_path("banners", f"{variant}{ext}"))

    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if os.path.exists(candidate):
            return candidate
    return None


def fetch_steam_image_candidates(query):
    term = (query or "").strip()
    if not term:
        return []

    params = urlencode({"term": term, "l": "russian", "cc": "RU"})
    request = Request(f"{STEAM_SEARCH_URL}?{params}", headers=HTTP_HEADERS)
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8", errors="ignore"))

    items = payload.get("items", [])[:18]
    results = []
    seen_urls = set()
    for item in items:
        app_id = item.get("id")
        title = item.get("name") or term
        candidate_urls = []
        if app_id:
            candidate_urls.append(f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg")
        if item.get("tiny_image"):
            candidate_urls.append(item["tiny_image"])

        image_url = next((url for url in candidate_urls if url and url not in seen_urls), None)
        if not image_url:
            continue
        seen_urls.add(image_url)
        results.append({"title": title, "app_id": app_id, "image_url": image_url})
    return results


def load_remote_pil_image(url):
    request = Request(url, headers=HTTP_HEADERS)
    with urlopen(request, timeout=20) as response:
        raw = response.read()
    image = Image.open(io.BytesIO(raw))
    image.load()
    return image


def save_banner_for_game(game_title, image_url):
    banner_dir = app_path("banners")
    if not os.path.exists(banner_dir):
        os.makedirs(banner_dir)

    image = load_remote_pil_image(image_url).convert("RGB")
    target_path = build_banner_path(game_title)
    image.save(target_path, format="JPEG", quality=92)
    return target_path


def open_banner_picker(game_title, on_saved=None, parent=None):
    picker = tk.Toplevel(parent or root)
    picker.title("Подбор фото игры")
    picker.geometry("860x520")
    picker.resizable(False, False)
    picker.grab_set()

    query_var = tk.StringVar(value=game_title or "")
    results = []
    preview_state = {"img": None, "selected_index": None}

    top_frame = ttk.Frame(picker, padding=10)
    top_frame.pack(fill=tk.X)

    ttk.Label(top_frame, text="Название игры").pack(side=tk.LEFT)
    query_entry = ttk.Entry(top_frame, textvariable=query_var, width=45)
    query_entry.pack(side=tk.LEFT, padx=8)

    body = ttk.Frame(picker, padding=(10, 0, 10, 10))
    body.pack(fill=tk.BOTH, expand=True)

    left = ttk.Frame(body)
    left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    listbox = tk.Listbox(left, font=("Segoe UI", 10))
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar = ttk.Scrollbar(left, orient=tk.VERTICAL, command=listbox.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    listbox.config(yscrollcommand=scrollbar.set)

    right = ttk.Frame(body)
    right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(12, 0))

    preview_label = ttk.Label(right, text="Выберите изображение из списка", anchor="center")
    preview_label.pack(fill=tk.BOTH, expand=True)
    source_label = ttk.Label(right, text="", wraplength=330)
    source_label.pack(fill=tk.X, pady=(8, 0))

    def update_preview(event=None):
        selection = listbox.curselection()
        if not selection:
            preview_state["selected_index"] = None
            return
        idx = selection[0]
        if idx >= len(results):
            return
        candidate = results[idx]
        preview_state["selected_index"] = idx
        try:
            preview_image = load_remote_pil_image(candidate["image_url"]).convert("RGB")
            preview_image.thumbnail((360, 210))
            preview_photo = ImageTk.PhotoImage(preview_image)
            preview_label.config(image=preview_photo, text="")
            preview_label.image = preview_photo
            preview_state["img"] = preview_photo
            source_label.config(text=f"{candidate['title']} (Steam AppID: {candidate.get('app_id') or 'n/a'})")
        except Exception as ex:
            preview_label.config(image="", text=f"Не удалось загрузить превью.\n{ex}")
            preview_label.image = None
            preview_state["img"] = None

    def search_action():
        term = query_var.get().strip()
        if not term:
            messagebox.showwarning("Поиск", "Введите название игры.")
            return

        listbox.delete(0, tk.END)
        preview_label.config(image="", text="Ищем изображения...")
        preview_label.image = None
        source_label.config(text="")
        picker.update_idletasks()

        try:
            found = fetch_steam_image_candidates(term)
        except Exception as ex:
            messagebox.showerror("Ошибка", f"Не удалось выполнить поиск изображений.\n{ex}")
            return

        results.clear()
        results.extend(found)
        if not results:
            preview_label.config(image="", text="Изображения не найдены.")
            return

        for candidate in results:
            app_id = candidate.get("app_id")
            suffix = f" [AppID: {app_id}]" if app_id else ""
            listbox.insert(tk.END, f"{candidate['title']}{suffix}")

        listbox.selection_clear(0, tk.END)
        listbox.selection_set(0)
        update_preview()

    def save_selected():
        idx = preview_state.get("selected_index")
        if idx is None or idx >= len(results):
            messagebox.showwarning("Выбор", "Сначала выберите изображение в списке.")
            return

        candidate = results[idx]
        try:
            saved_path = save_banner_for_game(game_title or query_var.get(), candidate["image_url"])
        except Exception as ex:
            messagebox.showerror("Ошибка", f"Не удалось сохранить изображение.\n{ex}")
            return

        messagebox.showinfo("Сохранено", f"Изображение сохранено:\n{saved_path}")
        if on_saved:
            on_saved(saved_path)
        picker.grab_release()
        picker.destroy()

    controls = ttk.Frame(picker, padding=(10, 0, 10, 10))
    controls.pack(fill=tk.X)
    ttk.Button(controls, text="Найти", command=search_action).pack(side=tk.LEFT)
    ttk.Button(controls, text="Сохранить выбранное", command=save_selected).pack(side=tk.RIGHT)

    listbox.bind("<<ListboxSelect>>", update_preview)
    query_entry.bind("<Return>", lambda _event: search_action())
    query_entry.focus_set()
    search_action()

def load_games(_filename=None):
    rows = fetch_all_games()
    games = []
    for row in rows:
        g = {
            "id": row["id"],
            "название": row["title"] or "",
            "год": str(row["release_year"]) if row["release_year"] is not None else "",
            "жанр": row["genre"] or "",
            "разработчик": row["developer"] or "",
            "платформы": row["platforms"] or "",
            "рейтинг": f"{row['rating']} / 10" if row["rating"] is not None else "",
            "описание": row["description"] or "",
        }
        games.append(g)
    return games

def save_games_to_file(current_games):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("TRUNCATE TABLE games")

    insert_sql = """
        INSERT INTO games
        (title, release_year, genre, developer, platforms, rating, description, image_path)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    for g in current_games:
        title = g.get("название", "").strip()
        year_str = g.get("год", "").strip()
        release_year = int(year_str) if year_str.isdigit() else None
        genre = g.get("жанр", "").strip() or None
        developer = g.get("разработчик", "").strip() or None
        platforms = g.get("платформы", "").strip() or None
        rating_raw = g.get("рейтинг", "").strip()
        rating = None
        if rating_raw:
            try:
                rating_str = rating_raw.split("/")[0].strip().replace(",", ".")
                rating = float(rating_str)
            except Exception:
                rating = None

        description = g.get("описание", "").strip() or None
        image_path = get_existing_banner_path(title) or (build_banner_path(title) if title else None)

        cursor.execute(
            insert_sql,
            (title, release_year, genre, developer, platforms, rating, description, image_path)
        )

    conn.commit()
    cursor.close()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def load_users():
    return {}

def save_users(_data):
    pass

def ensure_default_admin():
    import hashlib
    user = fetch_user_by_username("admin")
    if not user:
        pwd_hash = hashlib.sha256("admin123".encode("utf-8")).hexdigest()
        create_user("admin", pwd_hash, "admin")

def register_user(username, password, role="user"):
    import hashlib
    pwd_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    create_user(username, pwd_hash, role)

def authenticate_user(username, password):
    import hashlib
    user = fetch_user_by_username(username)
    if not user:
        return None

    pwd_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

    if user.get("password_hash") == pwd_hash:
        return {
            "id": user.get("id"),
            "username": user.get("username"),
            "role": user.get("role", "user"),
        }
    return None

def toggle_theme():
    global current_theme
    current_theme = "flatly" if current_theme == "darkly" else "darkly"
    root.style.theme_use(current_theme)
    theme_btn.config(text="☀" if current_theme == "darkly" else "🌙")

def open_drawing_pad():
    win = tk.Toplevel(root)
    win.title("Заметка")
    win.geometry("400x400")
    win.resizable(False, False)

    canvas = tk.Canvas(win, bg="white", width=400, height=350)
    canvas.pack()

    img = Image.new("RGB", (400, 350), "white")
    draw = ImageDraw.Draw(img)
    last = [None, None]

    def press(event):
        last[0], last[1] = event.x, event.y

    def move(event):
        x, y = event.x, event.y
        if last[0] is not None:
            canvas.create_line(last[0], last[1], x, y, width=2)
            draw.line((last[0], last[1], x, y), fill="black", width=2)
        last[0], last[1] = x, y

    def release(event):
        last[0], last[1] = None, None

    canvas.bind("<Button-1>", press)
    canvas.bind("<B1-Motion>", move)
    canvas.bind("<ButtonRelease-1>", release)

    def save():
        notes_dir = app_path("notes")
        if not os.path.exists(notes_dir):
            os.mkdir(notes_dir)
        i = 1
        while os.path.exists(app_path("notes", f"note_{i}.png")):
            i += 1
        img.save(app_path("notes", f"note_{i}.png"))
        messagebox.showinfo("Сохранено", f"Заметка сохранена: note_{i}.png")
        win.destroy()

    ttk.Button(win, text="Сохранить", command=save).pack(pady=5)

games = load_games("games.txt")
filtered_games = []
users = load_users()
ensure_default_admin()
current_user = None
auth_window = None
current_theme = "darkly"
base_title = "Gamepedia"

root = ttk.Window(themename=current_theme)
try:
    root.iconbitmap(bundle_path("icon.ico"))
except tk.TclError:
    pass
root.title(base_title)
root.geometry("1280x720")
root.resizable(False, False)

top = ttk.Frame(root, padding=5)
top.pack(side=tk.TOP, fill=tk.X)

search_var = tk.StringVar()
letter_var = tk.StringVar(value="A - Z")
rating_var = tk.StringVar(value="Рейтинг")
year_var = tk.StringVar(value="Год")
genre_var = tk.StringVar(value="Жанр")
platform_var = tk.StringVar(value="Платформа")

def on_entry_click(event):
    if search_var.get() == "Поиск...":
        search_entry.delete(0, tk.END)
        search_entry.config(foreground="white")

def on_focusout(event):
    if not search_entry.get():
        search_entry.insert(0, "Поиск...")
        search_entry.config(foreground="gray")

search_var = tk.StringVar()
search_entry = ttk.Entry(top, textvariable=search_var, width=30)
search_entry.insert(0, "Поиск...")
search_entry.config(foreground="gray")
search_entry.bind("<FocusIn>", on_entry_click)
search_entry.bind("<FocusOut>", on_focusout)
search_entry.pack(side=tk.LEFT, padx=(5, 10))

letter_box = ttk.Combobox(top, textvariable=letter_var, width=5, state="readonly")
letter_box["values"] = ["A - Z"] + [chr(i) for i in range(ord('A'), ord('Z')+1)]
letter_box.pack(side=tk.LEFT, padx=(5, 10))

actions_frame = ttk.Frame(top)
actions_frame.pack(side=tk.RIGHT, padx=(5, 0))

add_btn = ttk.Button(actions_frame, text="Требуется вход", width=18)
add_btn.config(state=tk.DISABLED)
add_btn.pack(side=tk.LEFT)

logout_btn = ttk.Button(actions_frame, text="Выйти", width=7)
logout_btn.config(state=tk.DISABLED)
logout_btn.pack(side=tk.LEFT, padx=(10, 0))

top_buttons_frame = ttk.Frame(top)
top_buttons_frame.pack(side=tk.RIGHT, padx=(5, 5))

favorites_list_btn = ttk.Button(
    top_buttons_frame,
    text="Мои избранные",
    width=16,
    state=tk.DISABLED,
)
favorites_list_btn.pack(side=tk.LEFT)

theme_btn = ttk.Button(top, text="🌙", width=3, command=toggle_theme)
theme_btn.pack(side=tk.RIGHT, padx=(5, 10))

note_btn = ttk.Button(top, text="🖊️", width=3, command=open_drawing_pad)
note_btn.pack(side=tk.RIGHT, padx=(5, 5))

platform_box = ttk.Combobox(top, textvariable=platform_var, width=11, state="readonly")
platform_box.pack(side=tk.RIGHT, padx=(10, 5))

year_box = ttk.Combobox(top, textvariable=year_var, width=5, state="readonly")
year_box.pack(side=tk.RIGHT, padx=(0, 0))

genre_box = ttk.Combobox(top, textvariable=genre_var, width=18, state="readonly")
genre_box.pack(side=tk.RIGHT, padx=(0, 10))

rating_box = ttk.Combobox(top, textvariable=rating_var, width=13, state="readonly")
rating_box["values"] = ["Рейтинг", "Сначала высокий", "Сначала низкий"]
rating_box.pack(side=tk.RIGHT, padx=(10, 10))

paned = ttk.Panedwindow(root, orient=HORIZONTAL)
paned.pack(fill=BOTH, expand=True)

left = ttk.Frame(paned, padding=10)
paned.add(left, weight=1)

game_list = tk.Listbox(left, font=("Segoe UI", 11))
game_list.pack(fill=BOTH, expand=True)

buttons_frame = ttk.Frame(left)
buttons_frame.pack(fill=tk.X, pady=(10, 0))

favorites_btn = ttk.Button(
    buttons_frame,
    text="⭐ В избранное",
    state=tk.DISABLED,
)
favorites_btn.pack(fill=tk.X)

right = ttk.Frame(paned, padding=10)
banner_label = ttk.Label(right)
banner_label.pack(pady=(0, 10))
info = ttk.Text(right, wrap="word", font=("Segoe UI", 12), state="disabled")
info.pack(fill=BOTH, expand=True)
paned.add(right, weight=3)

def parse_rating(g):
    raw = g.get("рейтинг", "")
    try:
        rating_str = raw.split("/")[0].strip().replace(",", ".")
        return float(rating_str)
    except Exception:
        return 0.0

def update_list(*_):
    global filtered_games
    filtered_games = []

    query = search_var.get().lower()
    if query == "поиск...":
        query = ""
    letter = letter_var.get()
    gnr = genre_var.get()
    rating_sort = rating_var.get()
    plat = platform_var.get()
    year = year_var.get()
    game_list.delete(0, tk.END)

    for g in games:
        title = g.get("название", "").lower()
        genre = g.get("жанр", "")
        plats = g.get("платформы", "")

        if query and query not in title:
            continue
        if year != "Год" and g.get("год", "") != year:
            continue
        if gnr != "Жанр":
            genre_list = [g_.strip().lower() for g_ in genre.split("/")]
            if gnr.lower() not in genre_list:
                continue
        if plat != "Платформа":
            plat_list = [p.strip().lower() for p in plats.split(",")]
            if plat.lower() not in plat_list:
                continue
        if letter != "A - Z":
            if not g.get("название", "").upper().startswith(letter.upper()):
                continue

        filtered_games.append(g)

    if rating_sort == "Сначала высокий":
        filtered_games.sort(key=parse_rating, reverse=True)
    elif rating_sort == "Сначала низкий":
        filtered_games.sort(key=parse_rating)
    else:
        filtered_games.sort(key=lambda g: g.get("название", "").lower())

    for g in filtered_games:
        game_list.insert(tk.END, g.get("название", "Без названия"))

def show_info(_):
    idxs = game_list.curselection()
    if not idxs:
        return
    idx = idxs[0]
    if idx >= len(filtered_games):
        return
    g = filtered_games[idx]
    txt = f"""Название: {g.get('название', '')}
Год: {g.get('год', '')}
Жанр: {g.get('жанр', '')}
Разработчик: {g.get('разработчик', '')}
Платформы: {g.get('платформы', '')}
Рейтинг: {g.get('рейтинг', '')}

Описание:
{g.get('описание', '')}"""
    info.config(state="normal")
    info.delete("1.0", "end")
    info.insert("end", txt)
    info.config(state="disabled")

    banner_path = get_existing_banner_path(g.get("название"))
    if banner_path and os.path.exists(banner_path):
        img = Image.open(banner_path).resize((350, 200))
        banner = ImageTk.PhotoImage(img)
        banner_label.config(image=banner)
        banner_label.image = banner
    else:
        banner_label.config(image='', text="(Баннер не найден)")

def update_user_state():
    if current_user:
        role = current_user.get("role", "user")
        readable_role = "Админ" if role == "admin" else "Пользователь"
        root.title(f"{base_title} - {current_user['username']} ({readable_role})")
        logout_btn.config(state=tk.NORMAL)
        favorites_btn.config(state=tk.NORMAL)
        favorites_list_btn.config(state=tk.NORMAL)
        if role == "admin":
            add_btn.config(text="Админ-панель", state=tk.NORMAL)
        else:
            add_btn.config(text="Предложить игру", state=tk.NORMAL)
    else:
        root.title(base_title)
        logout_btn.config(state=tk.DISABLED)
        add_btn.config(text="Требуется вход", state=tk.DISABLED)
        favorites_btn.config(state=tk.DISABLED)
        favorites_list_btn.config(state=tk.DISABLED)

def handle_primary_action():
    if not current_user:
        messagebox.showwarning("Требуется вход", "Авторизуйтесь, чтобы продолжить.")
        return
    if current_user.get("role") == "admin":
        open_admin_panel()
    else:
        open_propose_game()

def logout():
    global current_user
    current_user = None
    update_user_state()
    root.after(0, open_login_window)

def open_registration_window(parent):
    reg_win = tk.Toplevel(parent)
    reg_win.title("Регистрация")
    reg_win.geometry("320x220")
    reg_win.resizable(False, False)
    reg_win.grab_set()

    user_var = tk.StringVar()
    pass_var = tk.StringVar()
    confirm_var = tk.StringVar()

    ttk.Label(reg_win, text="Логин").grid(row=0, column=0, sticky="w", padx=10, pady=5)
    user_entry = ttk.Entry(reg_win, textvariable=user_var)
    user_entry.grid(row=0, column=1, padx=10, pady=5)

    ttk.Label(reg_win, text="Пароль").grid(row=1, column=0, sticky="w", padx=10, pady=5)
    pass_entry = ttk.Entry(reg_win, textvariable=pass_var, show="*")
    pass_entry.grid(row=1, column=1, padx=10, pady=5)

    ttk.Label(reg_win, text="Повторите пароль").grid(row=2, column=0, sticky="w", padx=10, pady=5)
    confirm_entry = ttk.Entry(reg_win, textvariable=confirm_var, show="*")
    confirm_entry.grid(row=2, column=1, padx=10, pady=5)

    def submit():
        username = user_var.get().strip()
        password = pass_var.get().strip()
        confirm = confirm_var.get().strip()

        if not username or not password:
            messagebox.showerror("Ошибка", "Логин и пароль не могут быть пустыми.")
            return

        if password != confirm:
            messagebox.showerror("Ошибка", "Пароли не совпадают.")
            return

        existing = fetch_user_by_username(username)
        if existing:
            messagebox.showerror("Ошибка", "Пользователь с таким именем уже существует.")
            return

        register_user(username, password)
        messagebox.showinfo("Успех", "Регистрация прошла успешно. Теперь можно войти.")
        reg_win.grab_release()
        reg_win.destroy()


    ttk.Button(reg_win, text="Зарегистрироваться", command=submit).grid(row=3, column=0, columnspan=2, pady=15)
    user_entry.focus_set()

def open_login_window():
    global auth_window, current_user
    if auth_window and auth_window.winfo_exists():
        return

    root.withdraw()
    login_win = tk.Toplevel(root)
    auth_window = login_win
    login_win.title("Вход в Gamepedia")
    login_win.geometry("320x220")
    login_win.resizable(False, False)
    login_win.grab_set()

    user_var = tk.StringVar()
    pass_var = tk.StringVar()

    ttk.Label(login_win, text="Логин").pack(pady=(15, 5))
    user_entry = ttk.Entry(login_win, textvariable=user_var)
    user_entry.pack(padx=20, fill=tk.X)

    ttk.Label(login_win, text="Пароль").pack(pady=(10, 5))
    pass_entry = ttk.Entry(login_win, textvariable=pass_var, show="*")
    pass_entry.pack(padx=20, fill=tk.X)

    def attempt_login():
        global current_user, auth_window
        username = user_var.get().strip()
        password = pass_var.get().strip()
        if not username or not password:
            messagebox.showerror("Ошибка", "Введите логин и пароль.")
            return
        data = authenticate_user(username, password)
        if not data:
            messagebox.showerror("Ошибка", "Неверный логин или пароль.")
            return
        current_user = {
            "id": data.get("id"),
            "username": username,
            "role": data.get("role", "user"),
        }
        login_win.grab_release()
        login_win.destroy()
        auth_window = None
        update_user_state()
        root.deiconify()
        messagebox.showinfo("Добро пожаловать", f"Вы вошли как {username}.")

    def close_app():
        global auth_window
        login_win.grab_release()
        login_win.destroy()
        auth_window = None
        root.destroy()

    ttk.Button(login_win, text="Войти", command=attempt_login).pack(pady=(15, 5))
    ttk.Button(login_win, text="Регистрация", command=lambda: open_registration_window(login_win)).pack(pady=(0, 10))
    login_win.bind("<Return>", lambda event: attempt_login())
    login_win.protocol("WM_DELETE_WINDOW", close_app)
    user_entry.focus_set()

def open_game_form(title, on_submit, initial=None, submit_text="Сохранить"):
    form = tk.Toplevel(root)
    form.title(title)
    form.geometry("420x480")
    form.resizable(False, False)
    form.grab_set()
    form.grid_columnconfigure(1, weight=1)

    widgets = {}
    row = 0
    for label, key in GAME_FIELDS:
        ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=5)
        if label == "Описание":
            widget = tk.Text(form, width=35, height=6, wrap="word")
            widget.grid(row=row, column=1, padx=10, pady=5)
            if initial:
                widget.insert("1.0", initial.get(key, ""))
        else:
            widget = ttk.Entry(form, width=35)
            widget.grid(row=row, column=1, padx=10, pady=5, sticky="we")
            if initial:
                widget.insert(0, initial.get(key, ""))
        widgets[key] = widget
        row += 1

    def submit():
        data = {}
        for label, key in GAME_FIELDS:
            widget = widgets[key]
            if label == "Описание":
                value = widget.get("1.0", tk.END).strip()
            else:
                value = widget.get().strip()
            data[key] = value
        if on_submit:
            result = on_submit(data)
            if result is not False:
                form.grab_release()
                form.destroy()

    ttk.Button(form, text=submit_text, command=submit).grid(row=row, column=0, columnspan=2, pady=15)
    return form

def open_propose_game():
    if not current_user:
        messagebox.showwarning("Требуется вход", "Авторизуйтесь, чтобы предложить игру.")
        return

    def on_submit(data):
        create_proposal(current_user["username"], data)
        messagebox.showinfo("Спасибо", "Предложение сохранено и отправлено администратору.")
        return True

    open_game_form("Предложить игру", on_submit=on_submit, submit_text="Отправить")

def add_selected_game_to_favorites():
    if not current_user:
        messagebox.showwarning("Требуется вход", "Авторизуйтесь, чтобы использовать избранное.")
        return

    sel = game_list.curselection()
    if not sel:
        messagebox.showwarning("Выбор", "Выберите игру в списке.")
        return

    idx = sel[0]
    if idx >= len(filtered_games):
        messagebox.showerror("Ошибка", "Не удалось определить выбранную игру. Обновите список и попробуйте снова.")
        return

    game = filtered_games[idx]
    game_id = game.get("id")
    if game_id is None:
        messagebox.showerror("Ошибка", "У этой игры нет ID. Проверьте загрузку из базы.")
        return

    user_id = current_user.get("id")
    if user_id is None:
        messagebox.showerror("Ошибка", "У пользователя нет ID. Проверьте авторизацию.")
        return

    if is_favorite(user_id, game_id):
        if messagebox.askyesno("Избранное", "Эта игра уже в избранном. Удалить из избранного?"):
            remove_favorite(user_id, game_id)
            messagebox.showinfo("Избранное", "Игра удалена из избранного.")
    else:
        add_favorite(user_id, game_id)
        messagebox.showinfo("Избранное", "Игра добавлена в избранное.")

def open_favorites_window():
    global current_user

    if not current_user:
        messagebox.showwarning("Требуется вход", "Авторизуйтесь, чтобы смотреть избранное.")
        return

    user_id = current_user.get("id")
    if user_id is None:
        messagebox.showerror("Ошибка", "У пользователя нет ID. Проверьте авторизацию.")
        return

    fav_games = fetch_user_favorite_games(user_id)

    win = tk.Toplevel(root)
    win.title("Мои избранные игры")
    win.geometry("500x400")

    listbox = tk.Listbox(win, font=("Segoe UI", 11))
    listbox.pack(fill=tk.BOTH, expand=True)

    if not fav_games:
        listbox.insert(tk.END, "У вас пока нет избранных игр.")
    else:
        for g in fav_games:
            title = g["title"] or ""
            year = g["release_year"] or ""
            listbox.insert(tk.END, f"{title} ({year})")


def open_admin_panel():
    if not current_user or current_user.get("role") != "admin":
        messagebox.showerror("Отказано", "Доступно только администраторам.")
        return

    panel = tk.Toplevel(root)
    panel.title("Админ-панель")
    panel.geometry("700x420")
    panel.resizable(False, False)

    list_frame = ttk.Frame(panel, padding=10)
    list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    listbox = tk.Listbox(list_frame, font=("Segoe UI", 11))
    listbox.pack(fill=tk.BOTH, expand=True)

    btn_frame = ttk.Frame(panel, padding=10)
    btn_frame.pack(side=tk.RIGHT, fill=tk.Y)

    def refresh_list():
        listbox.delete(0, tk.END)
        for g in games:
            listbox.insert(tk.END, g.get("название", "Без названия"))

    def get_selected_index():
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("Выбор", "Сначала выберите игру в списке.")
            return None
        return selection[0]

    def add_game_action():
        def on_submit(data):
            games.append(data)
            save_games_to_file(games)
            update_list()
            refresh_list()
            messagebox.showinfo("Сохранено", "Игра успешно добавлена.")
            return True
        open_game_form("Добавить игру", on_submit=on_submit)

    def edit_game_action():
        idx = get_selected_index()
        if idx is None:
            return
        original = games[idx]
        def on_submit(data, position=idx):
            games[position] = data
            save_games_to_file(games)
            update_list()
            refresh_list()
            messagebox.showinfo("Сохранено", "Информация об игре обновлена.")
            return True
        open_game_form("Редактировать игру", on_submit=on_submit, initial=original)

    def delete_game_action():
        idx = get_selected_index()
        if idx is None:
            return
        title = games[idx].get("название", "игру")
        if messagebox.askyesno("Удаление", f"Удалить {title}?"):
            games.pop(idx)
            save_games_to_file(games)
            update_list()
            refresh_list()
            messagebox.showinfo("Готово", "Игра удалена.")

    def remove_duplicates_action():
        global games
        deleted = delete_duplicate_games_by_title()
        if deleted > 0:
            games = load_games()
            update_list()
            refresh_list()
            messagebox.showinfo("Дубликаты", f"Удалено {deleted} повторяющихся записей.")
        else:
            messagebox.showinfo("Дубликаты", "Повторяющихся записей не найдено.")

    def pick_banner_action():
        idx = get_selected_index()
        if idx is None:
            return
        title = (games[idx].get("название") or "").strip()
        if not title:
            messagebox.showwarning("Выбор", "У выбранной игры нет названия.")
            return

        def on_banner_saved(_saved_path):
            update_list()
            refresh_list()
            selected = game_list.curselection()
            if selected:
                show_info(None)

        open_banner_picker(title, on_saved=on_banner_saved, parent=panel)

    def view_proposals():
        rows = fetch_all_proposals()

        win = tk.Toplevel(panel)
        win.title("Предложенные игры")
        win.geometry("800x450")
        win.resizable(False, False)

        left = ttk.Frame(win, padding=5)
        left.pack(side=tk.LEFT, fill=tk.Y)

        listbox = tk.Listbox(left, font=("Segoe UI", 11), width=35)
        listbox.pack(fill=tk.BOTH, expand=True)

        right = ttk.Frame(win, padding=5)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        details = tk.Text(right, wrap="word")
        details.pack(fill=tk.BOTH, expand=True)

        btn_frame = ttk.Frame(right)
        btn_frame.pack(fill=tk.X, pady=5)

        for row in rows:
            listbox.insert(tk.END, f"{row['id']}: {row['title']}")

        def show_selected(event=None):
            sel = listbox.curselection()
            if not sel:
                return
            idx = sel[0]
            row = rows[idx]

            details.config(state="normal")
            details.delete("1.0", tk.END)

            rating = row["rating"]
            rating_str = f"{rating} / 10" if rating is not None else ""

            text_block = []
            text_block.append(f"Название: {row['title']}")
            text_block.append(f"Год: {row['release_year'] or ''}")
            text_block.append(f"Жанр: {row['genre'] or ''}")
            text_block.append(f"Разработчик: {row['developer'] or ''}")
            text_block.append(f"Платформы: {row['platforms'] or ''}")
            text_block.append(f"Рейтинг: {rating_str}")
            text_block.append("")
            text_block.append("Описание:")
            text_block.append(row["description"] or "")
            text_block.append("")
            text_block.append(f"Предложено пользователем: {row['username']}")
            text_block.append(f"Дата: {row['created_at']}")
            details.insert("1.0", "\n".join(text_block))

            details.config(state="disabled")

        listbox.bind("<<ListboxSelect>>", show_selected)

        if rows:
            listbox.selection_set(0)
            show_selected()
        else:
            details.config(state="normal")
            details.insert("1.0", "Пока нет предложенных игр.")
            details.config(state="disabled")

        def add_to_games():
            sel = listbox.curselection()
            if not sel:
                messagebox.showwarning("Выбор", "Выберите предложение.")
                return

            idx = sel[0]
            row = rows[idx]

            game = {
                "название": row["title"] or "",
                "год": str(row["release_year"]) if row["release_year"] is not None else "",
                "жанр": row["genre"] or "",
                "разработчик": row["developer"] or "",
                "платформы": row["platforms"] or "",
                "рейтинг": f"{row['rating']} / 10" if row["rating"] is not None else "",
                "описание": row["description"] or "",
            }

            global games
            games.append(game)
            save_games_to_file(games)
            update_list()
            refresh_list()

            messagebox.showinfo("Добавлено", f"Игра «{game['название']}» добавлена в базу.")

            delete_proposal(row["id"])
            rows.pop(idx)
            listbox.delete(idx)
            details.config(state="normal")
            details.delete("1.0", tk.END)
            details.config(state="disabled")

        def delete_proposal_action():
            sel = listbox.curselection()
            if not sel:
                return
            idx = sel[0]
            row = rows[idx]
            if not messagebox.askyesno("Удаление", f"Удалить предложение «{row['title']}»?"):
                return

            delete_proposal(row["id"])
            rows.pop(idx)
            listbox.delete(idx)
            details.config(state="normal")
            details.delete("1.0", tk.END)
            details.config(state="disabled")

        ttk.Button(btn_frame, text="Добавить в базу игр", command=add_to_games).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Удалить предложение", command=delete_proposal_action).pack(side=tk.LEFT, padx=5)

    
    ttk.Button(btn_frame, text="Добавить", command=add_game_action).pack(fill=tk.X, pady=5)
    ttk.Button(btn_frame, text="Редактировать", command=edit_game_action).pack(fill=tk.X, pady=5)
    ttk.Button(btn_frame, text="Удалить", command=delete_game_action).pack(fill=tk.X, pady=5)
    ttk.Button(btn_frame, text="Подобрать фото", command=pick_banner_action).pack(fill=tk.X, pady=5)
    ttk.Button(btn_frame, text="Удалить дубликаты", command=remove_duplicates_action).pack(fill=tk.X, pady=5)
    ttk.Button(btn_frame, text="Предложения", command=view_proposals).pack(fill=tk.X, pady=5)


    refresh_list()


search_var.trace_add("write", update_list)
letter_var.trace_add("write", update_list)
rating_var.trace_add("write", update_list)
year_var.trace_add("write", update_list)
genre_var.trace_add("write", update_list)
platform_var.trace_add("write", update_list)
game_list.bind("<<ListboxSelect>>", show_info)

genres = sorted(set(
    genre.strip()
    for game in games
    for genre in game.get("жанр", "").split("/")
    if genre.strip()
))
platforms = sorted(set(p for g in games for p in g.get("платформы", "").split(", ")))

genre_box["values"] = ["Жанр"] + genres
platform_box["values"] = ["Платформа"] + platforms

years = sorted(set(g.get("год", "") for g in games if g.get("год", "").isdigit()), reverse=True)
year_box["values"] = ["Год"] + years

add_btn.config(command=handle_primary_action)
logout_btn.config(command=logout)
favorites_btn.config(command=add_selected_game_to_favorites)
favorites_list_btn.config(command=open_favorites_window)

update_user_state()
update_list()
open_login_window()
root.mainloop()

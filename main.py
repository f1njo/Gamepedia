import os
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from PIL import Image, ImageDraw, ImageTk

def load_games(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, 'r', encoding='utf-8') as f:
        blocks = f.read().strip().split("\n\n")
    games = []
    for block in blocks:
        g = {}
        for line in block.split("\n"):
            if ':' in line:
                k, v = line.split(':', 1)
                g[k.strip().lower()] = v.strip()
        if g:
            games.append(g)
    return games

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
        if not os.path.exists("notes"):
            os.mkdir("notes")
        i = 1
        while os.path.exists(f"notes/note_{i}.png"):
            i += 1
        img.save(f"notes/note_{i}.png")
        messagebox.showinfo("Сохранено", f"Заметка сохранена: note_{i}.png")
        win.destroy()

    ttk.Button(win, text="Сохранить", command=save).pack(pady=5)

games = load_games("games.txt")
filtered_games = []
current_theme = "darkly"

root = ttk.Window(themename=current_theme)
root.iconbitmap("icon.ico")
root.title("Gamepedia")
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

add_btn = ttk.Button(top, text="+", width=3, command=lambda: open_add_game())
add_btn.pack(side=tk.RIGHT)

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

paned = ttk.PanedWindow(root, orient=HORIZONTAL)
paned.pack(fill=BOTH, expand=True)

left = ttk.Frame(paned, padding=10)
paned.add(left, weight=1)

game_list = tk.Listbox(left, font=("Segoe UI", 11))
game_list.pack(fill=BOTH, expand=True)

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

    banner_path = f"banners/{g.get('название')}.jpg"
    if os.path.exists(banner_path):
        img = Image.open(banner_path).resize((350, 200))
        banner = ImageTk.PhotoImage(img)
        banner_label.config(image=banner)
        banner_label.image = banner
    else:
        banner_label.config(image='', text="(Баннер не найден)")


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

def open_add_game():
    add_win = tk.Toplevel(root)
    add_win.title("Добавить игру")
    add_win.geometry("390x460")
    add_win.resizable(False, False)
    fields = {
        "Название": tk.StringVar(),
        "Год": tk.StringVar(),
        "Жанр": tk.StringVar(),
        "Разработчик": tk.StringVar(),
        "Платформы": tk.StringVar(),
        "Рейтинг": tk.StringVar(),
        "Описание": tk.StringVar()
    }
    row = 0
    for lbl, var in fields.items():
        ttk.Label(add_win, text=lbl).grid(row=row, column=0, sticky="w", padx=10, pady=5)
        if lbl == "Описание":
            desc = tk.Text(add_win, width=30, height=5)
            desc.grid(row=row, column=1, padx=10, pady=5)
        else:
            ttk.Entry(add_win, textvariable=var, width=30).grid(row=row, column=1, padx=10, pady=5)
        row += 1

    def save():
        new = ""
        for lbl, var in fields.items():
            val = desc.get("1.0", tk.END).strip() if lbl == "Описание" else var.get().strip()
            new += f"{lbl}: {val}\n"
        new += "\n"
        with open("games.txt", "a", encoding="utf-8") as f:
            f.write(new)
        global games
        games = load_games("games.txt")
        update_list()
        add_win.destroy()
    ttk.Button(add_win, text="Сохранить", command=save).grid(row=row, column=0, columnspan=2, pady=15)

update_list()
root.mainloop()

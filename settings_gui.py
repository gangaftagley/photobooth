#!/usr/bin/env python3
"""settings_gui.py -- Tkinter settings screen for photo booth configuration."""

import tkinter as tk
from tkinter import ttk
from config import load_config, save_config, get_available_images

COLOR_PRESETS = {
    'Navy': [46, 65, 95],
    'White': [255, 255, 255],
    'Red': [200, 30, 30],
    'Black': [0, 0, 0],
    'Gold': [212, 175, 55],
}


def _rgb_to_hex(rgb):
    """Convert [r, g, b] list to #rrggbb hex string."""
    return '#%02x%02x%02x' % (rgb[0], rgb[1], rgb[2])


def _find_preset_name(color_list):
    """Find the preset name matching an RGB list, or 'Navy' as fallback."""
    for name, rgb in COLOR_PRESETS.items():
        if rgb == color_list:
            return name
    return 'Navy'


def run_settings():
    """
    Show settings GUI. Blocks until user clicks Start Booth.
    Returns the saved config dict.
    """
    config = load_config()

    root = tk.Tk()
    root.title("Photo Booth Settings")
    root.geometry("800x480")
    root.configure(bg='#2c3e50')

    try:
        root.attributes('-fullscreen', True)
    except Exception:
        pass  # fullscreen may not work on all platforms

    # Styling
    label_opts = {'font': ('Helvetica', 16), 'bg': '#2c3e50', 'fg': '#ecf0f1'}
    entry_font = ('Helvetica', 16)

    # Title
    tk.Label(root, text="Photo Booth Settings",
             font=('Helvetica', 24, 'bold'), bg='#2c3e50', fg='#ecf0f1').place(x=20, y=15)

    # --- Banner Text ---
    tk.Label(root, text="Banner Text:", **label_opts).place(x=30, y=80)
    banner_var = tk.StringVar(value=config['display']['banner_text'])
    tk.Entry(root, textvariable=banner_var, font=entry_font, width=30).place(x=250, y=80)

    # --- Text Color ---
    tk.Label(root, text="Text Color:", **label_opts).place(x=30, y=130)
    color_var = tk.StringVar(value=_find_preset_name(config['display']['text_color']))

    style = ttk.Style()
    style.configure('Color.TCombobox', font=entry_font)

    color_combo = ttk.Combobox(root, textvariable=color_var,
                                values=list(COLOR_PRESETS.keys()),
                                font=entry_font, state='readonly', width=12)
    color_combo.place(x=250, y=130)

    swatch = tk.Canvas(root, width=40, height=30, highlightthickness=1,
                       highlightbackground='#ecf0f1')
    swatch.place(x=480, y=132)

    def update_swatch(*_args):
        name = color_var.get()
        if name in COLOR_PRESETS:
            swatch.configure(bg=_rgb_to_hex(COLOR_PRESETS[name]))

    color_var.trace_add('write', update_swatch)
    update_swatch()

    # --- Screen Background ---
    tk.Label(root, text="Screen BG:", **label_opts).place(x=30, y=180)
    all_images = get_available_images()
    screen_var = tk.StringVar(value=config['display']['screen_image'])
    ttk.Combobox(root, textvariable=screen_var, values=all_images,
                 font=entry_font, state='readonly', width=28).place(x=250, y=180)

    # --- Print Template ---
    tk.Label(root, text="Print Template:", **label_opts).place(x=30, y=230)
    template_var = tk.StringVar(value=config['printing']['template_image'])
    ttk.Combobox(root, textvariable=template_var, values=all_images,
                 font=entry_font, state='readonly', width=28).place(x=250, y=230)

    # --- Paper Tray Count ---
    tk.Label(root, text="Paper Tray Count:", **label_opts).place(x=30, y=280)
    tray_var = tk.IntVar(value=config['printing']['paper_tray_count'])
    tk.Spinbox(root, from_=1, to=50, textvariable=tray_var,
               font=entry_font, width=5).place(x=250, y=280)

    # --- Reset Paper Counter ---
    tk.Label(root, text="Prints Done:", **label_opts).place(x=30, y=330)
    prints_label = tk.Label(root, text=str(config['state']['images_printed']),
                            font=('Helvetica', 16, 'bold'), bg='#2c3e50', fg='#e74c3c')
    prints_label.place(x=250, y=330)

    def reset_counter():
        config['state']['images_printed'] = 0
        config['state']['paper_bundles_loaded'] = 1
        prints_label.configure(text='0')

    tk.Button(root, text="Reset Counter", command=reset_counter,
              font=('Helvetica', 14), bg='#e74c3c', fg='white',
              width=14).place(x=330, y=325)

    # --- Start Booth Button ---
    def on_start():
        config['display']['banner_text'] = banner_var.get()
        name = color_var.get()
        config['display']['text_color'] = COLOR_PRESETS.get(name, [46, 65, 95])
        config['display']['screen_image'] = screen_var.get()
        config['printing']['template_image'] = template_var.get()
        config['printing']['paper_tray_count'] = tray_var.get()
        save_config(config)
        root.destroy()

    tk.Button(root, text="Start Booth", command=on_start,
              font=('Helvetica', 22, 'bold'), bg='#27ae60', fg='white',
              width=14, height=2, activebackground='#2ecc71').place(x=520, y=380)

    # --- Quit Button ---
    def on_quit():
        root.destroy()
        raise SystemExit(0)

    tk.Button(root, text="Quit", command=on_quit,
              font=('Helvetica', 14), bg='#7f8c8d', fg='white',
              width=8).place(x=30, y=400)

    root.mainloop()
    return load_config()


if __name__ == '__main__':
    result = run_settings()
    print("Settings saved:", result)

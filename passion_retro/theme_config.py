import copy

THEME_CONFIGS = {
    "default": {
        "name": "Classic",
        "extends": "default",
        "layout": {
            "navbar": "left",  # top, left, right, none
            "left_menu": True,  # True, False
            "right_menu": True,  # True, False
            "menu_type": "vertical",  # vertical, horizontal
        },
        "css_vars": {
            "colors": {
                "primary": "#2a5caa",
                "secondary": "#5588cc",
                "bg_body": "#d6dde8",
                "bg_container": "#ffffff",
                "text_primary": "#2c2c2c",
            },
        },
    },
    "00s": {
        "name": "Années 2000",
        "extends": "default",
        "layout": {
            "navbar": "top",
            "left_menu": True,
            "right_menu": True,
            "menu_type": "horizontal",
        },
        "css_vars": {
            "colors": {
                "primary": "#ff6600",
                "bg_body": "#0d0d0d",
                "bg_container": "#1a1a1a",
            },
        },
    },
    "modern": {
        "name": "Modern",
        "extends": "default",
        "layout": {
            "navbar": "left",
            "left_menu": True,
            "right_menu": True,
            "menu_type": "vertical",
        },
        "css_vars": {
            "colors": {
                "primary": "#2c3e50",
                "secondary": "#3498db",
                "bg_body": "#ecf0f1",
                "bg_container": "#ffffff",
                "text_primary": "#2c3e50",
            },
        },
    },
    "80s": {
        "name": "Années 80",
        "extends": "default",
        "layout": {
            "navbar": "top",
            "left_menu": True,
            "right_menu": True,
            "menu_type": "vertical",
        },
        "css_vars": {
            "colors": {
                "primary": "#ff00ff",
                "bg_body": "#000000",
                "bg_container": "#000033",
            },
        },
    },
    "retrogame": {
        "name": "RetroGame",
        "extends": "default",
        "layout": {
            "navbar": "top",
            "left_menu": True,
            "right_menu": True,
            "menu_type": "vertical",
        },
        "css_vars": {
            "colors": {
                "primary": "#00cc66",
                "bg_body": "#0a0c10",
                "bg_container": "#0e1318",
            },
        },
    },
    "retrorpg": {
        "name": "Retro RPG",
        "extends": "default",
        "layout": {
            "navbar": "top",
            "left_menu": True,
            "right_menu": True,
            "menu_type": "horizontal",
        },
        "css_vars": {
            "colors": {
                "primary": "#2a5caa",
            },
        },
    },
    "rpg": {
        "name": "RPG SNES/GBA",
        "extends": "default",
        "layout": {
            "navbar": "top",
            "left_menu": True,
            "right_menu": True,
            "menu_type": "vertical",
        },
        "css_vars": {
            "colors": {
                "primary": "#1a3d5c",
                "secondary": "#3a6a9a",
                "bg_body": "#0a0a1a",
                "bg_container": "#0d1b2a",
                "text_primary": "#e8e0d0",
            },
        },
    },
    "vhs": {
        "name": "VHS Glitch",
        "extends": "default",
        "layout": {
            "navbar": "top",
            "left_menu": True,
            "right_menu": True,
            "menu_type": "vertical",
        },
        "css_vars": {
            "colors": {
                "primary": "#00e5ff",
                "secondary": "#ff006e",
                "bg_body": "#0a0a0a",
                "bg_container": "#111111",
                "text_primary": "#e0e0e0",
            },
        },
    },
}


def get_theme_config(theme_name):
    if theme_name not in THEME_CONFIGS:
        theme_name = "default"

    config = copy.deepcopy(THEME_CONFIGS[theme_name])

    if config.get("extends"):
        base_config = copy.deepcopy(
            THEME_CONFIGS.get(config["extends"], THEME_CONFIGS["default"])
        )
        base_config.pop("name", None)
        base_config.pop("extends", None)

        if "layout" in base_config and "layout" in config:
            base_config["layout"].update(config["layout"])

        if "css_vars" in base_config and "css_vars" in config:
            for key in config["css_vars"]:
                if key in base_config["css_vars"]:
                    base_config["css_vars"][key].update(config["css_vars"][key])

        config.update(base_config)
        config.pop("extends", None)

    return config


def get_layout_config(theme_name):
    config = get_theme_config(theme_name)
    return config.get("layout", {})

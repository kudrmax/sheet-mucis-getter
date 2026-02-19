from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

CHOOSE_SHEETS = "Выбрать ноты"
UPLOAD_SHEETS = "Загрузить ноты"
CIFROVKI = "Цифровки"


def get_start_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=CHOOSE_SHEETS), KeyboardButton(text=UPLOAD_SHEETS)],
            [KeyboardButton(text=CIFROVKI)],
        ],
        resize_keyboard=True,
    )


NUMBER_EMOJI = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def get_folders_inline_keyboard(
    folders: list[dict], selected_ids: list[str]
) -> InlineKeyboardMarkup:
    use_numbers = len(selected_ids) >= 2
    buttons = []
    for folder in folders:
        if folder["id"] in selected_ids:
            if use_numbers:
                idx = selected_ids.index(folder["id"])
                mark = NUMBER_EMOJI[idx] if idx < len(NUMBER_EMOJI) else f"({idx + 1})"
            else:
                mark = "\u2705"
        else:
            mark = "\u2b1c"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{mark} {folder['name']}",
                    callback_data=f"folder_toggle:{folder['id']}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(text="Выбрать все", callback_data="select_all"),
            InlineKeyboardButton(
                text="Скачать выбранные", callback_data="download_selected"
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_upload_folders_inline_keyboard(
    folders: list[dict],
) -> InlineKeyboardMarkup:
    buttons = []
    for folder in folders:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=folder["name"],
                    callback_data=f"upload_folder:{folder['id']}:{folder['name']}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="Создать папку", callback_data="create_upload_folder"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirm_filename_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подтвердить", callback_data="confirm_filename"
                ),
                InlineKeyboardButton(
                    text="Переименовать", callback_data="rename_filename"
                ),
            ]
        ]
    )


def get_more_files_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Загрузить ещё", callback_data="upload_more"
                ),
                InlineKeyboardButton(text="Готово", callback_data="upload_done"),
            ]
        ]
    )


# ── Cifrovka keyboards ──


def get_cifrovka_folder_keyboard(
    folders: list[dict],
) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f["name"], callback_data=f"cif_f:{i}")]
        for i, f in enumerate(folders)
    ]
    buttons.append(
        [InlineKeyboardButton(text="Назад", callback_data="cif_back")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cifrovka_actions_keyboard(has_cifrovka: bool) -> InlineKeyboardMarkup:
    if has_cifrovka:
        buttons = [
            [
                InlineKeyboardButton(text="Все версии", callback_data="cif_versions"),
                InlineKeyboardButton(text="Новая версия", callback_data="cif_new"),
            ],
            [
                InlineKeyboardButton(text="Редактировать", callback_data="cif_edit"),
                InlineKeyboardButton(text="Удалить", callback_data="cif_delete"),
            ],
            [InlineKeyboardButton(text="Назад", callback_data="cif_back")],
        ]
    else:
        buttons = [
            [InlineKeyboardButton(text="Создать", callback_data="cif_new")],
            [InlineKeyboardButton(text="Назад", callback_data="cif_back")],
        ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cifrovka_versions_keyboard(
    versions: list,
) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=f"v{v.version} ({v.created_at[:10]}) — {v.author}",
            callback_data=f"cif_v:{v.version}",
        )]
        for v in versions
    ]
    buttons.append(
        [InlineKeyboardButton(text="Назад", callback_data="cif_back_view")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cifrovka_delete_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да, удалить", callback_data="cif_del_yes"),
                InlineKeyboardButton(text="Отмена", callback_data="cif_del_no"),
            ]
        ]
    )

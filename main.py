import os
import pyzipper
import rarfile
import shutil
import subprocess
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from WinRAR import *
# إعدادات البوت
api_id = 27963121  # ضع api_id الخاص بك
api_hash = "aff4a583ee5107e6c0fb7e1f02b45652"  # ضع api_hash الخاص بك
bot_token = "6498365850:AAFd_LZGlalk2-IDUmkhSleX6_2S3OCaHQM"  # ضع توكن البوت الخاص بك

# إنشاء الجلسة مع البوت
app = Client("zip_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# دالة لضغط الملفات مع كلمة مرور للملفات zip و rar
def compress_files_with_password(file_paths, custom_name=None, password=None, format="zip"):
    if custom_name:
        compressed_path = os.path.join(os.path.dirname(file_paths[0]), custom_name + f".{format}")
    else:
        compressed_path = file_paths[0] + f".{format}"

    if format == "zip":
        # ضغط ملفات ZIP
        if password:
            with pyzipper.AESZipFile(compressed_path, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zipf:
                zipf.setpassword(password.encode())
                for file_path in file_paths:
                    zipf.write(file_path, os.path.basename(file_path))
        else:
            with pyzipper.AESZipFile(compressed_path, 'w', compression=pyzipper.ZIP_DEFLATED) as zipf:
                for file_path in file_paths:
                    zipf.write(file_path, os.path.basename(file_path))
    elif format == "rar":
        rar_path = shutil.which("rar")  # استخدام المسار التلقائي لبرنامج rar
        if rar_path is None:
            raise FileNotFoundError("لم يتم العثور على برنامج rar. تأكد من أنه مثبت على النظام.")
        if password:
            subprocess.run([rar_path, 'a', '-p' + password, compressed_path] + file_paths)
        else:
            subprocess.run([rar_path, 'a', compressed_path] + file_paths)

    return compressed_path



def extract_file(file_path, password=None):
    extracted_folder = file_path + "_extracted"
    os.makedirs(extracted_folder, exist_ok=True)

    if file_path.endswith('.zip'):
        with pyzipper.AESZipFile(file_path, 'r') as zip_ref:
            if password:
                zip_ref.setpassword(password.encode())
            zip_ref.extractall(extracted_folder)
    elif file_path.endswith('.rar'):
        with rarfile.RarFile(file_path, 'r') as rar_ref:
            try:
                if password:
                    rar_ref.extractall(extracted_folder, pwd=password)
                else:
                    rar_ref.extractall(extracted_folder)
            except rarfile.RarWrongPassword:
                raise RuntimeError("كلمة المرور غير صحيحة أو الملف تالف.")

    return extracted_folder



pending_compression = {}
pending_extraction = {}


@app.on_message(filters.document)
async def handle_file(client, message):
    user_id = message.from_user.id
    file_path = await message.download()

    if file_path.endswith(".zip") or file_path.endswith(".rar"):
        pending_extraction[user_id] = {"file_path": file_path, "mode": "request_password"}
        await message.reply_text("الملف مضغوط. إذا كان هناك كلمة مرور، الرجاء إرسالها، أو إرسال 'بدون' إذا لم يكن هناك.")
    else:
        if user_id not in pending_compression:
            pending_compression[user_id] = {"file_paths": [], "mode": "choose_format"}
        pending_compression[user_id]["file_paths"].append(file_path)
        
        await message.reply_text(f"تم إضافة الملف {os.path.basename(file_path)}. أرسل مزيدًا من الملفات أو اختر تنسيق الضغط (ZIP أو RAR):")

        if len(pending_compression[user_id]["file_paths"]) == 1:
            buttons = [
                [InlineKeyboardButton("ضغط بصيغة ZIP", callback_data="zip")],
                [InlineKeyboardButton("ضغط بصيغة RAR", callback_data="rar")]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            await message.reply_text("اختر تنسيق الضغط:", reply_markup=reply_markup)


@app.on_callback_query()
async def handle_callback_query(client, query):
    user_id = query.from_user.id

    if user_id in pending_compression:
        data = pending_compression[user_id]
        file_paths = data["file_paths"]

        if data["mode"] == "choose_format":
            format = query.data
            pending_compression[user_id] = {"file_paths": file_paths, "format": format, "mode": "compress_name"}
            await query.message.edit_text("الرجاء إرسال الاسم الذي ترغب في استخدامه للملف المضغوط.")


@app.on_message(filters.text & filters.private)
async def handle_custom_name_or_password(client, message):
    user_id = message.from_user.id

    if user_id in pending_extraction:
        data = pending_extraction.pop(user_id)
        file_path = data["file_path"]
        password = None if message.text == "بدون" else message.text

        try:
            extracted_folder = extract_file(file_path, password)
            await message.reply_text("تم فك ضغط الملف بنجاح.")


            for root, dirs, files in os.walk(extracted_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    await message.reply_document(file_path)

            os.remove(file_path)
            shutil.rmtree(extracted_folder)

        except (pyzipper.BadZipFile, rarfile.BadRarFile, RuntimeError):
            await message.reply_text("كلمة المرور غير صحيحة أو الملف تالف.")
            pending_extraction[user_id] = {"file_path": file_path, "mode": "request_password"}
            await message.reply_text("الرجاء إعادة إرسال كلمة المرور.")
        
    elif user_id in pending_compression:
        data = pending_compression.pop(user_id)
        file_paths = data["file_paths"]
        mode = data["mode"]

        if mode == "compress_name":
            custom_name = message.text
            format = data["format"]

            pending_compression[user_id] = {"file_paths": file_paths, "custom_name": custom_name, "mode": "password", "format": format}
            await message.reply_text("الرجاء إرسال كلمة المرور التي تريد استخدامها لحماية الملف. إذا كنت لا ترغب في تعيين كلمة مرور، أرسل 'بدون'.")
        elif mode == "password":
            custom_name = data["custom_name"]
            format = data["format"]
            password = None if message.text == "بدون" else message.text

            compressed_path = compress_files_with_password(file_paths, custom_name, password, format)

            await message.reply_document(compressed_path)

            for file_path in file_paths:
                os.remove(file_path)
            os.remove(compressed_path)

# بدء تشغيل البوت
app.run()

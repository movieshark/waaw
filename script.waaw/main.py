import codecs
from base64 import b64decode
from re import findall, search
from secrets import SystemRandom
from sys import argv
from tempfile import NamedTemporaryFile
from urllib.parse import parse_qsl, quote, urlencode

import captcha_window
import xbmc
import xbmcaddon
import xbmcgui
from requests import Session

user_agent = "Mozilla/5.0 (Windows NT 10.0; WOW64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.5666.197 Safari/537.36"
sec_ch_ua = '"Google Chrome";v="113", "Chromium";v="113", "Not=A?Brand";v="24"'

addon = xbmcaddon.Addon()
random = SystemRandom()
handle = "[%s]" % addon.getAddonInfo("name")
session = Session()
session.headers.update(
    {
        "accept-language": "en-US,en;q=0.9",
        "sec-ch-ua": sec_ch_ua,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": user_agent,
    }
)


def decrypt(input: str):
    if "." not in input:
        input = input[1:]
        s2 = ""
        for i in range(0, len(input), 3):
            character = "\\u0" + input[i : i + 3]
            s2 += codecs.decode(character, "unicode_escape")
    return s2


def random_sha1():
    return "".join([random.choice("0123456789abcdef") for x in range(40)])


def get_video_by_id(id: str):
    headers = {
        "authority": "waaw.ac",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,\
        application/signed-exchange;v=b3;q=0.7",
        "accept-language": "en-US,en;q=0.9",
    }
    r = session.get("https://waaw.ac/e/" + id, headers=headers)
    # videoid = "51676240",
    video_id = search(r"'videoid': '(\d+)'", r.text).group(1)
    # adbn = '139933',
    adbn = search(r"adbn = '(\d+)'", r.text).group(1)
    subtitles = []
    for link, lang in findall(r'file2sub\("([^"]+)","([^"]+)",', r.text):
        subtitles.append(
            {
                "link": link,
                "lang": lang,
            }
        )

    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "origin": "https://waaw.ac",
        "referer": "https://waaw.ac/e/" + id,
        "x-requested-with": "XMLHttpRequest",
    }
    data = {"videoid": video_id, "videokey": id, "width": 400, "height": 400}

    r = session.post(
        "https://waaw.ac/player/get_player_image.php", headers=headers, json=data
    )

    json_data = r.json()

    if json_data.get("try_again") == "1":
        dialog = xbmcgui.Dialog()
        dialog.ok(
            addon.getAddonInfo("name"),
            "Too many attempts. Please try again in a bit.",
        )
        return
    hash = json_data["hash_image"]
    image = json_data["image"].replace("data:image/jpeg;base64,", "")
    image = b64decode(image + "=====", validate=False)

    window = captcha_window.CaptchaWindow(image, 400, 400)
    window.doModal()

    if not window.finished:
        return

    x = window.solution_x
    y = window.solution_y

    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "origin": "https://waaw.ac",
        "referer": "https://waaw.ac/e/" + id,
        "x-requested-with": "XMLHttpRequest",
    }
    data = {
        "adb": adbn,
        "sh": random_sha1(),  # ?
        "ver": "4",
        "secure": "0",
        "htoken": "",
        "v": id,
        "token": "",
        "gt": "",
        "embed_from": "0",
        "wasmcheck": 1,
        "adscore": "",
        "click_hash": quote(hash),
        "clickx": x,
        "clicky": y,
    }
    r = session.post("https://waaw.ac/player/get_md5.php", headers=headers, json=data)
    json_data = r.json()
    if json_data.get("try_again") == "1":
        dialog = xbmcgui.Dialog()
        dialog.ok(
            addon.getAddonInfo("name"),
            "Wrong captcha. Please try again.",
        )
        return

    obf_link = json_data["obf_link"]
    decrypted_link = decrypt(obf_link)

    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "origin": "https://waaw.ac",
        "referer": "https://waaw.ac/",
    }
    url = "https:" + decrypted_link
    r = session.get("https:" + decrypted_link, headers=headers)
    subtitle_files = []
    for subtitle in subtitles:
        response = session.get(subtitle["link"], headers=headers)
        temp_file = NamedTemporaryFile(suffix=".srt")
        temp_file.write(response.content)
        temp_file.flush()
        subtitle_files.append(
            temp_file,
        )

    player = xbmc.Player()
    player.play(url + ".mp4.m3u8|" + urlencode(headers))
    # wait for player to start
    while not player.isPlaying():
        xbmc.sleep(1000)
    for subtitle_file in subtitle_files:
        player.setSubtitles(subtitle_file.name)
    # wait for player to stop
    while player.isPlaying():
        xbmc.sleep(1000)
    for subtitle_file in subtitle_files:
        subtitle_file.close()


def self_test():
    dialog = xbmcgui.Dialog()
    dialog.notification(
        addon.getAddonInfo("name"),
        "No video id found. Doing self-test.",
    )
    # prompt for video id from user
    video_id = dialog.input(
        addon.getAddonInfo("name"),
        defaultt="cwZV66C60UJs",
        type=xbmcgui.INPUT_TYPE_TEXT,
    )
    if not video_id:
        return
    get_video_by_id(video_id)


if __name__ == "__main__":
    if len(argv) < 3:
        self_test()
        exit()
    params = dict(parse_qsl(argv[2].replace("?", "")))
    video_id = params["video_id"]

    if video_id:
        get_video_by_id(video_id)
    else:
        dialog = xbmcgui.Dialog()
        dialog.notification(addon.getAddonInfo("name"), "No video id found.")

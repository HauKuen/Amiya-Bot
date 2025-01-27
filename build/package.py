import re
import os
import sys
import shutil
import zipfile
import pathlib
import subprocess

from urllib import request

ZIP_FILE_LIST = [
    'china_location.zip', 'chinese_char_dictionary.zip',
    'chinese_idiom.zip', 'chinese_word_dictionary.zip',
    'idf.zip',
    'pinyin_phrase.zip', 'sentiment_words.zip',
    'char_distribution.zip', 'word_distribution.zip',
    'word_topic_weight.zip', 'topic_word_weight.zip',
    'phone_location.zip', 'xiehouyu.zip',
    'pornography.zip']

version_file = '''# UTF-8
VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=({file_ver}, 0),
        mask=0x3f,
        flags=0x0,
        OS=0x4,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0)
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    u'040904B0',
                    [
                        StringStruct(u'CompanyName', u'AmiyaBot'),
                        StringStruct(u'ProductName', u'《明日方舟》QQ机器人'),
                        StringStruct(u'ProductVersion', u'{file_version}'),
                        StringStruct(u'FileDescription', u'《明日方舟》QQ机器人，https://www.amiyabot.com'),
                        StringStruct(u'FileVersion', u'{file_version}'),
                        StringStruct(u'OriginalFilename', u'AmiyaBot.exe'),
                        StringStruct(u'LegalCopyright', u'Github AmiyaBot 组织版权所有'),
                    ]
                )
            ]
        ),
        VarFileInfo([VarStruct(u'Translation', [2052, 1200])])
    ]
)
'''

platform = sys.platform

venv = 'venv/Lib/site-packages'
scripts = 'venv/Scripts'

if platform == 'linux':
    venv = 'venv/lib/python3.8/site-packages'
    scripts = 'venv/bin'

folder = 'package'


def build(version: str, force: bool = False, upload: bool = False):
    dist = f'{folder}/dist'
    jieba_copy = f'{folder}/jieba'
    local = os.path.abspath('/'.join(sys.argv[0].replace('\\', '/').split('/')[:-1]) or '.')

    try:
        cos_url = f'https://cos.amiyabot.com/package/release/latest-{platform}.txt'
        latest = str(request.urlopen(cos_url).read(), encoding='utf-8').strip('\r\n')
    except Exception as e:
        print(repr(e))
        latest = ''

    if not version:
        with open('.github/publish.txt', mode='r', encoding='utf-8') as ver:
            version = ver.read().strip('\r\n')

    if latest == version and not force:
        print('not new release.')
        return None

    setup_name = f'AmiyaBot-{version}-{platform}'

    if os.path.exists(dist):
        shutil.rmtree(dist)

    if os.path.exists(jieba_copy):
        shutil.rmtree(jieba_copy)

    os.makedirs(dist)
    os.makedirs(jieba_copy)

    shutil.copy(f'{venv}/jieba/dict.txt', f'{jieba_copy}/dict.txt')
    shutil.copytree('config', f'{dist}/config', dirs_exist_ok=True)
    shutil.copytree(os.path.abspath(f'{venv}/amiyabot/_assets').replace(' ', '\\ '), f'{dist}/_assets',
                    dirs_exist_ok=True)

    for item in ZIP_FILE_LIST:
        if not os.path.exists(f'{dist}/dictionary'):
            os.makedirs(f'{dist}/dictionary')
        print(f'moving {venv}/jionlp/dictionary/{item}')
        shutil.copy(f'{venv}/jionlp/dictionary/{item}', f'{dist}/dictionary/{item}')

    with open(f'{folder}/version.txt', mode='w+', encoding='utf-8') as vf:
        vf.write(
            version_file.format(
                file_ver=', '.join(re.findall(r'v(\d+).(\d+).(\d+)', version)[0]),
                file_version=version
            )
        )

    cmd = [
        f'cd {folder}'
    ]

    disc = folder.split(':')
    if len(disc) > 1:
        cmd.append(disc[0] + ':')

    data_files = [
        (os.path.abspath(jieba_copy).replace(' ', '\\ '), 'jieba')
    ]
    add_ico_cmd = f' -i {local}/amiya.ico'
    add_version_cmd = f' --version-file=version.txt'
    add_datas_cmd = ''.join([' --add-data=%s;%s' % df for df in data_files])
    playwright_install = f'set PLAYWRIGHT_BROWSERS_PATH=0 && {os.path.abspath(scripts)}/playwright install chromium'

    if platform == 'linux':
        add_ico_cmd = ''
        add_version_cmd = ''
        add_datas_cmd = ''.join([' --add-data=%s:%s' % df for df in data_files])
        playwright_install = f'PLAYWRIGHT_BROWSERS_PATH=0 {os.path.abspath(scripts)}/playwright install chromium'

    cmd += [
        f'pyi-makespec -F -n {setup_name}{add_ico_cmd}{add_version_cmd} {local}/amiya.py {add_datas_cmd}',
        f'{playwright_install}',
        f'{os.path.abspath(scripts)}/pyinstaller {setup_name}.spec'
    ]

    for cm in cmd:
        print('execute:', cm)

    build_process = subprocess.Popen('&&'.join(cmd), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    for line in build_process.stdout.readlines():
        print(line)

    pack_name = f'{setup_name}.zip'
    path = pathlib.Path(f'{folder}/{pack_name}')

    with zipfile.ZipFile(path, 'w') as pack:
        for root, dirs, files in os.walk(dist):
            for index, filename in enumerate(files):
                target = os.path.join(root, filename)
                pack.write(target, target.replace(dist + '\\', ''))

    os.remove(f'{folder}/version.txt')

    if upload:
        upload_pack('.github/publish.txt', path, pack_name)


def upload_pack(ver_file, package_file, package_name):
    from .uploadFile import COSUploader

    secret_id = os.environ.get('SECRETID')
    secret_key = os.environ.get('SECRETKEY')

    cos = COSUploader(secret_id, secret_key)

    cos.upload_file(package_file, f'package/release/{package_name}')
    cos.upload_file(ver_file, f'package/release/latest-{platform}.txt')

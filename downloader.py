import asyncio,aiohttp,aiofiles
from asyncio.tasks import ensure_future
from json import encoder
from json.decoder import JSONDecodeError
import json,os,logging,re
logging.basicConfig(level = logging.INFO,format = '[%(levelname)s] %(asctime)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
}

API_CHAPTER = 'https://api.copymanga.com/api/v3/comic/{pathword}/group/default/chapters?limit=500&offset=0&platform=3'
API_COMIC = 'https://api.copymanga.com/api/v3/comic/{pathword}/chapter2/{uuid}?platform=3'
COMIC_INDEX = 'https://www.copymanga.com/comic/{pathword}'

retry = 3 # 下载失败重试次数

g_chapters = {} # 章节缓存
g_download_failed = []

async def download(url,path):
    global g_download_failed
    if os.path.exists(path): # 下载过的跳过
        logger.info(f'Skip {path} which is downloaded.')
        return
    async with aiohttp.ClientSession(headers=headers) as session:
        for i in range(retry):
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        async with aiofiles.open(path,mode='wb') as f:
                            await f.write(await resp.read())
                            logger.info(f'{path} ok.')
                            return
                    else:
                        logger.warn(f'{path} error, error code:{resp.status}.')
            except Exception as e:
                logger.warn(f'Connect error when download {path}, error info:{str(e)}.')

        g_download_failed.append((url,path))
        logger.error(f'{path} download failed.')

async def fetch(session, url):
    for i in range(retry):
        try:
            async with session.get(url) as resp:
                return await resp.text()
        except:
            continue
    

async def get_title_by_pathword(pathword):
    async with aiohttp.ClientSession(headers=headers) as session:
        html = await fetch(session,COMIC_INDEX.format(pathword=pathword))
        title = re.search('<title>(.+?)</title>',html,re.S).group(1).strip()
        title = title[:title.find('-')]
        return title

async def get_chapters_uuid(pathword):
    """获取所有章节，以及对应的uuid
    Args:
        pathword: /comic/<pathword>/
        raw:      是否返回原始list
    Returns:
        [(chapter_name, uuid)]
    """
    global g_chapters
    if pathword in g_chapters:
        return g_chapters[pathword]

    async with aiohttp.ClientSession(headers=headers) as session:
        json_src = await fetch(session,API_CHAPTER.format(pathword=pathword))
    json_obj = json.loads(json_src)
    chapters = json_obj['results']['list'] # name uuid
    chapters = list(map(lambda x:(x['name'],x['uuid']),chapters))
    g_chapters[pathword] = chapters
    return chapters

async def get_chapter_uuid(pathword,chapter:str) -> str:
    """根据漫画和章节名获取章节uuid
    Args:
        pathword:     漫画的识别串
        chapter: "第x话"
    Returns:
        成功，返回chapter对应的uuid
        失败，返回''
    """
    chapters = await get_chapters_uuid(pathword)
    if chapter not in chapters:
        pass # TODO 
    # 这里遍历来找到对应章节，因为中间可能穿插各种奇怪的章节名
    for chapter in chapters:
        if chapter[0] == chapter:
            return chapter[1]
    return ''

async def get_pics_url(pathword,chapter_uuid:str) -> list[str]:
    """根据pathword,章节的uuid获取所有图片的url
    Args:
        pathword:     漫画的识别串
        chapter_uuid: 章节的uuid
    Returns:
        list(url)
    """
    async with aiohttp.ClientSession(headers=headers) as session:
        json_src = await fetch(session,API_COMIC.format(pathword=pathword,uuid=chapter_uuid))
    json_obj = json.loads(json_src)
    pic_urls = json_obj['results']['chapter']['contents']  # uuid url
    pic_urls = list(map(lambda x:x['url'],pic_urls))
    return pic_urls

async def download_chapter(pathword,chapter,chapter_uuid,manga_name=''):
    """下载一个章节
    Args:
        manga_name: 漫画名，用于本地文件夹的命名。如果保持空则自动获取
        chapter_uuid: 可省略为'' 如果省略则通过get_chapter_uuid获取
    """
    if pathword == '' or chapter == '':
        return
    if manga_name == '':
        manga_name = await get_title_by_pathword(pathword)
    folder = os.path.join(manga_name,chapter)
    # 目录不存在则创建
    if not os.path.exists(folder):
        os.makedirs(folder)
    if chapter_uuid in (None,''):
        chapter_uuid = await get_chapter_uuid(pathword,chapter)
    pic_urls = await get_pics_url(pathword,chapter_uuid)
    logger.info(f'Downloading {chapter}, {len(pic_urls)} pictures.')
    tasks = [asyncio.create_task(download(url,os.path.join(folder,f'{i+1}.jpg'))) for i,url in enumerate(pic_urls)]
    results = await asyncio.gather(*tasks)
    logger.info(f'{chapter} downloaded.')

async def download_chapters(pathword,chapter_range:str,manga_name=''):
    """下载多个章节
    Args:
        chapters: 第xx话-第xx话
    """
    if pathword == '' or chapter_range == '':
        return
    tasks = []
    download_flag = 0
    if manga_name == '':
        manga_name = await get_title_by_pathword(pathword)
    logger.info(f'Start downloading {manga_name}.')
    chapters = await get_chapters_uuid(pathword)
    if '-' not in chapter_range:
        bg = ed = chapter_range
    else:
        bg,ed = chapter_range.strip().split('-')
    for chapter in chapters:
        if chapter[0] == bg:
            download_flag = 1
        if download_flag == 0:
            continue
        elif download_flag == 1:
            tasks.append(asyncio.create_task(download_chapter(pathword,chapter[0],chapter[1],manga_name)))
        else:
            break
        if chapter[0] == ed:
            download_flag = 2
    await asyncio.gather(*tasks)

async def get_all_updated_manga():
    """获取追漫列表最新更新
        Returns:
            [(pathword:str,chapter_range:str)]
    """
    async def get_updated(pathword,curr):
        chapters = await get_chapters_uuid(pathword)
        bg = -1
        for i,chapter in enumerate(chapters):
            if chapter[0] == curr:
                bg = i + 1
        if bg == len(chapters):
            return (pathword,'')
        return (pathword,f'{chapters[bg][0]}-{chapters[-1][0]}')
    data = []
    try:
        with open('./watching.json','r',encoding='utf-8') as f:
            data = json.loads(f.read())
    except JSONDecodeError as e:
        logger.error('Read data.json error.')
    res = []
    for name in data:
        updated = await get_updated(name,data[name])
        if updated[1] == '':
            continue
        res.append(updated)
    return res

async def updated_watching():
    updated = await get_all_updated_manga()
    if len(updated) == 0:
        logger.info('No updated.')
    else:
        tasks = []
        with open('./watching.json','r',encoding='utf-8') as f:
            data = json.loads(f.read())
        for per in updated:
            tasks.append(asyncio.create_task(download_chapters(per[0],per[1])))
        await asyncio.gather(*tasks)
        for per in updated:
            data[per[0]] = per[1].split('-')[1]
        with open('./watching.json','w',encoding='utf-8') as f:
            f.write(json.dumps(data,indent=4,ensure_ascii=False))

async def re_download_failed():
    global g_download_failed
    tmp = g_download_failed
    g_download_failed = []
    for per in tmp:
        await download(per[0],per[1])

def main():
    global g_download_failed
    print("""
    ----------------------------
     CopyMangaDownloader  by:ck
     1. 更新追漫列表
     2. 下载漫画
     3. 重新下载失败列表
    ----------------------------
    """)
    loop = asyncio.get_event_loop()
    while True:
        mode = input('You want?[1/2/3]: ')
        if mode == '1':
            loop.run_until_complete(updated_watching())
        elif mode == '2':
            pathword = input('Pathword: ')
            chapter = input('Chapter: ')
            try:
                loop.run_until_complete(download_chapters(pathword,chapter))
            except Exception as e:
                logger.error(e)
            logger.info('Download finished.')
        elif mode == '3':
            loop.run_until_complete(re_download_failed())
        # 下载失败列表
        if len(g_download_failed) > 0:
            logger.warning(f'Failed list:{g_download_failed}')
        print('----------------------------')

if __name__ == '__main__':
    main()
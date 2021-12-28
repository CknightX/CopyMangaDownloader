import asyncio,aiohttp,aiofiles
import json,os,logging
logging.basicConfig(level = logging.INFO,format = '[%(levelname)s] %(asctime)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
}

API_CHAPTER = 'https://api.copymanga.com/api/v3/comic/{pathword}/group/default/chapters?limit=500&offset=0&platform=3'
API_COMIC = 'https://api.copymanga.com/api/v3/comic/{pathword}/chapter2/{uuid}?platform=3'

retry = 3 # 下载失败重试次数

async def download(url,path):
    async with aiohttp.ClientSession(headers=headers) as session:
        for i in range(retry):
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        async with aiofiles.open(path,mode='wb') as f:
                            await f.write(await resp.read())
                            logger.info(f'{path} ok.')
                            break
                    else:
                        logger.error(f'{path} error, error code:{resp.status}')
            except Exception as e:
                logger.error(f'Connect error when download {path}, error info:{str(e)}')

async def fetch(session, url):
    async with session.get(url) as resp:
        return await resp.text()

async def get_chapters_uuid(pathword):
    """获取所有章节，以及对应的uuid
    Args:
        pathword: /comic/<pathword>/
        raw:      是否返回原始list
    Returns:
        {chapter_name : uuid}
    """
    async with aiohttp.ClientSession(headers=headers) as session:
        json_src = await fetch(session,API_CHAPTER.format(pathword=pathword))
    json_obj = json.loads(json_src)
    chapters = json_obj['results']['list'] # name uuid
    chapters = list(map(lambda x:(x['name'],x['uuid']),chapters))
    return chapters

async def get_chapter_uuid(pathword,chapter:str):
    """根据漫画和章节名获取章节uuid
    Args:
        chapter: "第x话"
    Returns:
        chapter对应的uuid
    """
    chapters = await get_chapters_uuid(pathword)
    if chapter not in chapters:
        pass # TODO 
    # 这里遍历来找到对应章节，因为中间可能穿插各种奇怪的章节名
    for chapter in chapters:
        if chapter[0] == chapter:
            return chapter[1]
    return ''

async def get_pics_url(pathword,chapter_uuid:str):
    """根据章节的uuid获取所有图片的url
    Args:
        chapter_uuid: 章节的uuid
    Returns:
        list(图url)
    """
    async with aiohttp.ClientSession(headers=headers) as session:
        json_src = await fetch(session,API_COMIC.format(pathword=pathword,uuid=chapter_uuid))
    json_obj = json.loads(json_src)
    pic_urls = json_obj['results']['chapter']['contents']  # uuid url
    pic_urls = list(map(lambda x:x['url'],pic_urls))
    return pic_urls

async def download_chapter(pathword,chapter,chapter_uuid,manga_name):
    """下载一个章节
    Args:
        manga_name: 漫画名，用于本地文件夹的命名
        chapter_uuid: 可省略为'' 如果省略则通过get_chapter_uuid获取
    """
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

async def download_chapters(pathword,chapter_range:str,manga_name):
    """下载多个章节
    Args:
        chapters: 第xx话-第xx话
    """
    tasks = []
    download_flag = 0
    chapters = await get_chapters_uuid(pathword)
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

if __name__ == '__main__':
    pathword = 'tonghuabandenikaishiliaolianaimenggong'
    loop = asyncio.get_event_loop()
    loop.run_until_complete(download_chapters(pathword,'第01话-第17话','童話般的你開始了戀愛猛攻'))
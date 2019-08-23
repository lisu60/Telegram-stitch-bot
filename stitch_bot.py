#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import redis
import cv2
import io
import numpy as np
import datetime as dt
import config

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)


r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=config.REDIS_DB_NUM)


def start(update, context):
    update.message.reply_html(config.START_MSG)
    help(update, context)


def help(update, context):
    update.message.reply_text(config.HELP_MESSAGE)


def clear(update, context):
    r.delete(update.message.chat_id)
    update.message.reply_text('Pictures cleared. /help')
    logger.info('%d requested clear' % update.message.chat_id)


def stitch(update, context):
    logger.info('Stitching for %d' % update.message.chat_id)
    imgs = []
    for fid in r.lrange(update.message.chat_id, 0,-1):
        raw = update.message.bot.get_file(fid.decode('ascii')).download_as_bytearray()
        imgs.append(cv2.imdecode(np.fromstring(bytes(raw), np.uint8), cv2.IMREAD_COLOR))
    stitcher = cv2.Stitcher_create(cv2.Stitcher_SCANS)
    return_code, res = stitcher.stitch(tuple(imgs))
    del imgs


    if return_code == cv2.Stitcher_OK:
        status, raw_res=cv2.imencode('.png', res)
        now = dt.datetime.now();
        update.message.reply_document(io.BytesIO(raw_res.tobytes()), filename='stitched%s.png' % now.strftime('%Y%m%d%H%H%S'))
    elif return_code == cv2.Stitcher_ERR_NEED_MORE_IMGS:
        update.message.reply_text('Not enough images. Plz try screenshots with more overlap. /help')
        logger.info('Stitching failed for %d, not enough images' % update.message.chat_id)
    else:
        update.message.reply_text('Unknown error while stitching. Plz try again. /help')
        logger.warning('Stitching failed for %d, error code: %d' %(update.message.chat_id, return_code))
    r.delete(update.message.chat_id)



def store_photo(update, context):
    logger.info('Photo received from %d, update id: %d' % (update.message.chat_id, update.update_id))
    count = r.lpush(update.message.chat_id, max(update.message.photo, key=lambda x: x.file_size).file_id)
    r.expire(update.message.chat_id, 3600)
    update.message.reply_text('%d pictures uploaded' %count)


def store_document(update, context):
    logger.info('Document received from %d, update id: %d' % (update.message.chat_id, update.update_id))
    if update.message.document.mime_type.startswith('image'):
        count = r.lpush(update.message.chat_id, update.message.document.file_id)
        r.expire(update.message.chat_id, 3600)
        update.message.reply_text('%d pictures uploaded' %count)
    else:
        logger.info('Update %d: not image, discarding')


def echo(update, context):
    update.message.reply_text('photo received')
    f = update.message.document
    logger.info("%s %s" % (f.file_name, f.mime_type))
    f.get_file().download()


def error(update, context):
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main():
    updater = Updater(config.BOT_TOKEN, use_context=True)

    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("clear", clear))
    dp.add_handler(CommandHandler("stitch", stitch))
    dp.add_handler(CommandHandler("help", help))

    dp.add_handler(MessageHandler(Filters.private & Filters.photo, store_photo))
    dp.add_handler(MessageHandler(Filters.private & Filters.document, store_document))

    dp.add_error_handler(error)

    updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()

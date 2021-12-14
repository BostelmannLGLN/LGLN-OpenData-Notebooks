import os
from pathlib import Path
import imageio
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw
from tqdm import tqdm

from datetime import date
import locale
#locale.setlocale(locale.LC_ALL, 'de_DE.utf8')

from moviepy.editor import ImageClip, concatenate

import fnmatch
import requests
import pandas as pd

def add_banner(image_path, logo_path, out_path, name,
               image_date=None, min_date=None, max_date=None,
               add_bar=True, add_name=True, center_text=None, add_date=True,
               canvas_width=1200, canvas_height=1200, border=20, padding=20):

    image = Image.open(image_path)
    logo_left = Image.open(logo_path[0])
    logo_right = Image.open(logo_path[1])

    # Aspect Ratios
    canvas_ar = canvas_width / canvas_height
    image_ar = image.width / image.height

    if canvas_ar < image_ar:
        image_width = canvas_width
        image_height = image.height * (canvas_width / image.width)
    else:
        image_width = image.width * (canvas_height / image.height)
        image_height = canvas_height

    image = image.resize((int(image_width), int(image_height)))

    # Warning: Assumption that both logos have the same size
    canvas = Image.new('RGBA', (border + canvas_width + border,
                             border + canvas_height + padding + logo_right.height + border))
    canvas.paste(image, (border + int((canvas_width - image_width) / 2),
                         border + int((canvas_height - image.height) / 2)))
    canvas.paste(logo_left, (border, border + canvas_height + padding))
    canvas.paste(logo_right, (border + canvas_width - logo_right.width, border + canvas_height + padding))

    draw = ImageDraw.Draw(canvas)

    # Add Date and Name to the banner
    filepath = Path(image_path)

    image_d = date(int(image_date[0:4]), int(image_date[4:6]), int(image_date[6:8]))

    month = image_d.strftime('%B')
    #german name of the month. because #locale.setlocale(locale.LC_ALL, 'de_DE.utf8') does not work on CODE-DE Linux
    german_months = ['Null', 'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']
    month = german_months[image_d.month]
    
    german_date = f'{image_d.day}. {month} {image_d.year}'

    font = ImageFont.truetype("./fonts/ClearSans-Regular.ttf", 24) #TODO
    text_width, text_height = draw.textsize(german_date, font=font)

    if add_name:
        draw.text((border + 10, border + canvas_height + 10 + padding), f"{name}", (101, 106, 105), font=font)
    if center_text:
        draw.text((border + 320, border + canvas_height + 10 + padding), center_text, (101, 106, 105), font=font)
    if add_date:
        draw.text((border + (canvas_width-20)-text_width, border + canvas_height + 10 + padding), german_date, (0, 0, 0), font=font)

    # Add progress bar to the banner
    if min_date and max_date and add_bar:

        min_d = date(int(min_date[0:4]), int(min_date[4:6]), int(min_date[6:8]))
        max_d = date(int(max_date[0:4]), int(max_date[4:6]), int(max_date[6:8]))
        period = max_d - min_d
        max_days = period.days

        diff_d = image_d - min_d
        image_days = diff_d.days

        p = canvas_width / max_days
        box_width = image_days * p
        draw.rectangle(((border, border + canvas_height + padding), 
                        (border + box_width, border + canvas_height + 10 + padding)), 
                         fill="red")

    canvas = canvas.convert("RGBA")
    new_image = Image.new("RGBA", canvas.size, "WHITE")
    new_image.paste(canvas, (0, 0), canvas)

    new_image.convert('RGB').save(out_path)


def create_animation(image_list, dates, name='', animations_path=Path('.'),
               type='gif', duration=0.5, add_ban=True, center_text=None, add_name=True, add_bar=True,
               canvas_width=800, canvas_height=800, logo_path=None):
    images = []
    tmp_image_paths = []
    for file_name in tqdm(image_list, desc=f'Creating {name}.{type}'):
        abs_file_path = os.path.join(file_name)
        tmp_image_path = abs_file_path[:-4] + '_tmp.png'
        # Find 8-digit date in file_path
        date_string = [x for x in str(file_name).split("_") if x.isdigit() and len(x)==8]
        image_date = date_string[0]

        if add_ban:
            add_banner(abs_file_path, logo_path, tmp_image_path, name,
                       image_date, min_date=min(dates), max_date=max(dates),
                       add_bar=add_bar, add_name=add_name, center_text=center_text,
                       canvas_width=canvas_width, canvas_height=canvas_height)
        else:
            tmp_image_path = abs_file_path
        tmp_image_paths.append(tmp_image_path)

        images.append(imageio.imread(tmp_image_path))

    if type == 'gif':
        file_name = name + '.gif'
        out_file_path = animations_path / file_name
        imageio.mimsave(out_file_path, images, 'GIF-FI', quantizer='wu',
                        duration=duration, palettesize=256)
    elif type == 'mp4':
        clips = []
        for tmp_image_path in tmp_image_paths:
            clip = ImageClip(tmp_image_path).set_duration(duration)
            clips.append(clip)
        file_name = name + '.mp4'
        out_file_path = animations_path / file_name
        video = concatenate(clips, method="compose")
        print(out_file_path)
        video.write_videofile(str(out_file_path), fps=24) # TODO
        
    else:
        print('Use gif or mp4 as type')

    #TODO repair clean up
    #for temp_file in tmp_image_paths:
        #os.remove(temp_file)

    return out_file_path


def animate_tiles_from_cos(tile_nr, dates, 
           bucket_credentials='', tmp_path='', animations_path=Path('.'),
           type='mp4', channel='TCI_10m', duration=0.5, name=None,
           add_ban=True, add_bar=True, add_name=True, center_text='center_text',
           canvas_width=800, canvas_height=800, logo_path=None):
    
    animations_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    image_list = []
    
    endpoint_url = bucket_credentials['endpoint_url']
    bucket_name = bucket_credentials['name']

        
    for date in tqdm(dates, desc=f'Reading from COS bucket: {bucket_name}'):

        file_name = f'{tile_nr}_S2_{date}_{channel}.tif'
        
        tile_object_url = f'{tile_nr}/S2/{date}/{file_name}'
        tmp_file_path = tmp_path / tile_nr / 'S2' / date / file_name
        tmp_file_path.parent.mkdir(parents=True, exist_ok=True)

        request_url = endpoint_url + f'{bucket_name}/{tile_object_url}'
        request_object = requests.get(request_url)
        with open(tmp_file_path, 'wb') as writer:
            writer.write(request_object.content)
            
        image_list.append(tmp_file_path)  

    out_file_path = create_animation(image_list, dates, name=name, type=type, animations_path=animations_path,
                   duration=duration,
                   add_ban=add_ban, add_bar=add_bar, add_name=add_name, center_text=center_text,
                   canvas_width=canvas_width, canvas_height=canvas_height,
                   logo_path=logo_path)
    return out_file_path


def animate_tiles_local(storage_path, tile_nr, dates, animations_path='',
           type='mp4', channel='TCI_10m', duration=0.5, name=None,
           add_bar=True, add_name=True, add_km=True,
           canvas_width=800, canvas_height=800, logo_path=None):
                      
    image_list = []
    for date in dates:
        image_list.extend(list(storage_path.glob(f'{tile_nr}/S2/{date}/*{channel}.tif')))

    out_file_path = create_gif(image_list, dates, name=name, type=type, animations_path=animations_path,
                   duration=duration,
                   add_bar=add_bar, add_name=add_name, add_km=add_km,
                   canvas_width=canvas_width, canvas_height=canvas_height,
                   logo_path=logo_path)
    return out_file_path


def animate_mosaics_local(storage_path, mosaic_name, dates, animations_path='',
               type='mp4', duration=0.5, add_bar=True, add_name=True, add_km=True,
               canvas_width=0, canvas_height=0, logo_path=None):
    image_list = []
    for date in dates:
        image_list.extend(storage_path.glob(f'{mosaic_name}/*{mosaic_name}_{date}*.png'))
        
    out_path = create_gif(image_list, dates, name=mosaic_name, type=type, animations_path=animations_path,
                          duration=duration,
                          add_bar=add_bar, add_name=add_name, add_km=add_km,
                          canvas_width=canvas_width, canvas_height=canvas_height,
                          logo_path=logo_path)
    return out_path
from stock import *
from linebot.v3.messaging import (
    TemplateMessage,
    URIAction,
    CarouselTemplate,
    CarouselColumn
)

def ColTemplate(news_df):
    CarouselColumn_list = []
    for i in range(len(news_df)):
        titles = (news_df.iloc[i,1])[:35]+"..."
        contents = (news_df.iloc[i,2])[:55]+"..."
        ids = news_df.iloc[i,3]
        col = CarouselColumn(
                thumbnail_image_url = None,
                title=titles,
                text=contents,
                actions=[
                    URIAction(
                        label="查看新聞",
                        uri = f"https://news.cnyes.com/news/id/{ids}",
                    )
                ]
            )
        CarouselColumn_list.append(col)
    
    carouselTP = CarouselTemplate(
        columns=CarouselColumn_list
    )
    
    carouselMsg = TemplateMessage(
        alt_text = "新聞資訊",
        template=carouselTP
    )
    return carouselMsg
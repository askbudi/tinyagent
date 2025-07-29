# In 10 lines of code, you can extract data from a website source, and give GOOGLE_MAP_API to TinyAgent, so it does the whole research and analysis and just create a csv file for you.
#This example is based on a real story. MY friend was looking for a highly related resturant participating in a summer program. and legacy website didn't allow her to search, or filter by Google Maps Reviews, Pricing and ...
# TinyAgent came to the rescue, and in 10 lines of code, it extracted the data, and gave GOOGLE_MAP_API to TinyAgent, so it does the whole research and analysis and just create a csv file for you.
#
from tinyagent import TinyCodeAgent
import os
import asyncio



agent = TinyCodeAgent(
    model="o4-mini",
    api_key=os.environ.get("OPENAI_API_KEY"),
    ui="jupyter",
    authorized_imports=["json","pandas","requests"],
    local_execution=True,
    
)

async def run_example(page_content):
    GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")

    response =await agent.run("""
    Here is a page source of a website that has a list of resturants in Toronto. Participating in a summer program.
                            I need you to do the following:
                            1. Extract Resturant names, addresses and phone numbers from the page source. and save it in a dict in your python enviroment.
                            2. Use Google Maps API to get information about the resturants, number of reviews, and average rating are the most important ones but also include other information about it.
    3.  I need you to sort resturants based on their number of reviews and average rating. ( combination, rate 5 with 1 rate doesn't mean quality)                        
    --- 
                            Use your python enviroment to handle Google Maps API in code.
                            Important: You have to proccess the whole list of resturants., it is better to do a small section first to test the code and your approach and when you were sure about it you can do the whole list.
                            You are an agent , you need to get the job done yourself.
                            My Google Maps API key is:"{api_key}"

                            ---
                            <page_source>
                            {page_source}
                            </page_source>
    """.format(api_key=GOOGLE_MAPS_API_KEY, page_source=page_content))

    df = agent.code_provider._globals_dict['df']

    df.to_csv("resturants.csv")





page_content = page_content = """

## Participating Restaurants

Restaurant Name

Address

Telephone

1 Kitchen

550 Wellington St W

416-601-3533

12 Tables

1552 Avenue Rd

416-590-7819

612 Harlowe

612 Richmond St W

416-637-9998

7 Numbers Eglinton

516 Eglinton Ave W

416-322-5183

Aamara

1224 St Clair Ave W

416-651-0010

Abrielle

355 King St W

416-915-3760

Adega

33 Elm St

416-977-4338

Aera

8 Spadina Ave, #3800

647-258-5207

AGO Bistro

317 Dundas St W

416-979-6688

Alder

51 Camden St

416-637-3737

Alice Restaurant

488 College St

647-693-7730

Amano Italian Kitchen

65 Front St W

647-350-0092

Amano Trattoria

9 Church St

647-349-7297

Aria Ristorante

25 York St

416-363-2742

Arisu Korean BBQ & Sushi

584 Bloor St W

416-533-8104

Auberge du Pommier

4150 Yonge St

416-222-2220

AVIV Immigrant Kitchen

779 St Clair Ave W

416-922-2433

AYLA

794 Dundas St W, 2nd Fl

647-340-4999

Azhar Kitchen + Bar

96 Ossington Ave

647-503-1098

Azure Restaurant & Bar

225 Front St W

416-597-8142

Bangkok Garden

18 Elm St

416-977-6748

Bar Avelo

51 St Nicholas St

647-643-3132

Bar Bacan

369 Roncesvalles Ave

416-535-2222

Barnsteiner’s

1 Balmoral Ave

416-515-0551

Baro

485 King St W

416-363-8388

Bella Vista Trattoria

660 College St

416-532-2518

Bellona

276 Jane St

416-604-8777

Beso by Patria

478 King St W

416-367-0505

Biff’s Bistro

2 Front St E

416-860-0086

Bistro YYZ

970 Dixon Rd

416-675-7611

Black & Blue Restaurant

130 King St W

647-368-8283

Blu Ristorante

90 Avenue Rd

416-921-1471

Boccaccio Ristorante Italiano

901 Lawrence Ave W

416-781-1272

Bon Italia Trattoria & Cafe

595 Sheppard Ave E

647-247-8222

Bosk

188 University Ave

647-788-8281

Bridgette Bar Toronto

423 Wellington St W

647-258-5203

Brownes Bistro

1251 Yonge St

416-924-8132

Bukhara Grill

2241A Bloor St W

416-551-5199

Butter Chicken Factory

560 Parliament St

416-964-7583

Byblos Uptown

2537 Yonge St

416-487-4897

Cactus Club Cafe

77 Adelaide St W

647-748-2025

Café ZUZU

555 Dundas St E

416-815-2660

Canoe

66 Wellington St W, TD Bank Tower, 54th Fl

416-364-0054

Canteen

330 King St W

647-288-4710

Capocaccia Trattoria

1366 Yonge St

416-921-3141

Casa Barcelona

2980 Bloor St W

416-234-5858

Casa Madera

550 Wellington St W

416-601-3593

Casa Manila

879 York Mills Rd

416-443-9654

Ceci Bar

33 Yonge St

437-253-1613

Chiado

864 College St

416-538-1910

Chop Steakhouse & Bar

801 Dixon Rd

416-674-7500

Chotto Matte

161 Bay St

647-250-7087

Cibo Wine Bar King Street

522 King St W

416-504-3939

CKTL & CO

330 Bay St

416-363-3558

Clandestina Mexican Grill

2901 Dundas St W

647-348-6555

Clay Restaurant

111 Queen’s Park, 3rd Fl

416-586-8086

Comma

490 Queen St W

289-971-1255

Constantine

15 Charles St E

647-475-4436

CopaCabana Brazilian Steakhouse

150 Eglinton Ave E

416-916-2099

Coppi

3363 Yonge St

416-484-4464

Cucina Buca

2 St Clair Ave W

416-840-9822

Cucina di Paisano

865 York Mills Rd

416-222-5487

Curryish Tavern

783 Queen St W

416-392-7837

DaiLo

503 College St

647-341-8882

Dia Restautant & Lounge

387 Bloor St E

416-921-3333

Diwan

77 Wynford Dr

416-646-4670

Earls Sherway

199 North Queen St

647-249-6323

Edna + Vita

77 Adelaide St W

437-562-6099

EPOCH Bar & Kitchen Terrace

181 Wellington St W

416-572-8094

est Restaurant

729 Queen St E

416-465-3707

FIGO

295 Adelaide St W

647-748-3446

Fine Artisanal Wine Bar

226 Christie St

416-915-9463

Floga Estiatorio

1957 Kennedy Rd

416-335-9600

Flor 2 Tapas & Wine Bar

722 College St, Lower Level

416-516-2539

Florentia

579 Mount Pleasant Rd

416-908-6450

Fonda Lola

942 Queen St W

647-706-9105

Frenchy Bar et Brasserie

145 Richmond St W

416-860-6800

Function Bar and Kitchen

2291 Yonge St

416-440-4007

F’Amelia

12 Amelia St

416-323-0666

Gatsby by Windsor Arms

18 St Thomas St

416-971-9666

GEORGE

111C Queen St E

416-863-6006

Gladstone House Hotel

1214 Queen St W

416-531-4635

Goa Indian Farm Kitchen

2901 Bayview Ave

647-352-1661

Granite Brewery and Restaurant

245 Eglinton Ave E

416-322-0723

Han Ba Tang Korean Restaurant & Bar

4862 Yonge St

416-546-8218

Hawker

291 Augusta Ave

416-628-1905

Hey Lucy

295 King St W

416-979-1010

Hibachi

550 Wellington St W

416-367-3888

High Park Brewery

837 Runnymede Rd

647-398-9336

Hotel Ocho Bar and Restaurant

195 Spadina Ave

416-593-0885

Hothouse Restaurant & Bar

35 Church St

416-366-7800

Il Ponte

625 Queen St E

416-778-0404

Indian Street Food Co.

1701 Bayview Ave

416-322-3270

Insomnia

563 Bloor St W

416-588-3907

JaBistro

222 Richmond St W

647-748-0222

JOEY King St

20 King St W

647-678-5639

Joni Restaurant

4 Avenue Rd

647-948-3130

Jump

18 Wellington St W

416-363-3400

Kadak – Vibrant Indian Cuisine

2088 Yonge St

416-322-6227

Kalyvia Restaurant

420 Danforth Avenue

416-463-3333

"""
if __name__ == "__main__":
    asyncio.run(run_example(page_content))
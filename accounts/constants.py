"""
Fixed choice data used at registration and on the user profile.

Kept in one module so forms, models, templates, and migrations all share
the exact same lists.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

# Maximum length of the free-text field shown when "Other" is selected.
OTHER_INSTRUMENT_MAX_LENGTH = 15


class County(models.TextChoices):
    """All 32 historic counties of the island of Ireland."""

    ANTRIM = "antrim", _("Antrim")
    ARMAGH = "armagh", _("Armagh")
    CARLOW = "carlow", _("Carlow")
    CAVAN = "cavan", _("Cavan")
    CLARE = "clare", _("Clare")
    CORK = "cork", _("Cork")
    DONEGAL = "donegal", _("Donegal")
    DOWN = "down", _("Down")
    DUBLIN = "dublin", _("Dublin")
    FERMANAGH = "fermanagh", _("Fermanagh")
    GALWAY = "galway", _("Galway")
    KERRY = "kerry", _("Kerry")
    KILDARE = "kildare", _("Kildare")
    KILKENNY = "kilkenny", _("Kilkenny")
    LAOIS = "laois", _("Laois")
    LEITRIM = "leitrim", _("Leitrim")
    LIMERICK = "limerick", _("Limerick")
    LONDONDERRY = "londonderry", _("Londonderry")
    LONGFORD = "longford", _("Longford")
    LOUTH = "louth", _("Louth")
    MAYO = "mayo", _("Mayo")
    MEATH = "meath", _("Meath")
    MONAGHAN = "monaghan", _("Monaghan")
    OFFALY = "offaly", _("Offaly")
    ROSCOMMON = "roscommon", _("Roscommon")
    SLIGO = "sligo", _("Sligo")
    TIPPERARY = "tipperary", _("Tipperary")
    TYRONE = "tyrone", _("Tyrone")
    WATERFORD = "waterford", _("Waterford")
    WESTMEATH = "westmeath", _("Westmeath")
    WEXFORD = "wexford", _("Wexford")
    WICKLOW = "wicklow", _("Wicklow")


# Representative towns and cities for each county. Not every village —
# the main population centres plus well-known towns. The town name itself
# is stored on the user record (User.town_city).
TOWNS_BY_COUNTY = {
    County.ANTRIM: [
        "Antrim",
        "Ballycastle",
        "Ballyclare",
        "Ballymena",
        "Belfast",
        "Carrickfergus",
        "Crumlin",
        "Larne",
        "Lisburn",
        "Newtownabbey",
        "Portrush",
        "Randalstown",
    ],
    County.ARMAGH: [
        "Armagh",
        "Bessbrook",
        "Craigavon",
        "Crossmaglen",
        "Keady",
        "Lurgan",
        "Markethill",
        "Portadown",
        "Richhill",
        "Tandragee",
    ],
    County.CARLOW: [
        "Bagenalstown",
        "Borris",
        "Carlow",
        "Hacketstown",
        "Leighlinbridge",
        "Rathvilly",
        "Tullow",
    ],
    County.CAVAN: [
        "Bailieborough",
        "Ballyconnell",
        "Ballyjamesduff",
        "Belturbet",
        "Cavan",
        "Cootehill",
        "Kingscourt",
        "Virginia",
    ],
    County.CLARE: [
        "Ennis",
        "Ennistymon",
        "Kilkee",
        "Killaloe",
        "Kilrush",
        "Lahinch",
        "Lisdoonvarna",
        "Newmarket-on-Fergus",
        "Shannon",
        "Sixmilebridge",
    ],
    County.CORK: [
        "Ballincollig",
        "Bandon",
        "Bantry",
        "Carrigaline",
        "Charleville",
        "Clonakilty",
        "Cobh",
        "Cork City",
        "Fermoy",
        "Kinsale",
        "Macroom",
        "Mallow",
        "Midleton",
        "Mitchelstown",
        "Skibbereen",
        "Youghal",
    ],
    County.DONEGAL: [
        "Ballybofey",
        "Ballyshannon",
        "Buncrana",
        "Bundoran",
        "Carndonagh",
        "Donegal Town",
        "Dungloe",
        "Killybegs",
        "Letterkenny",
        "Moville",
    ],
    County.DOWN: [
        "Ballynahinch",
        "Banbridge",
        "Bangor",
        "Comber",
        "Downpatrick",
        "Dromore",
        "Hillsborough",
        "Holywood",
        "Kilkeel",
        "Newry",
        "Newtownards",
        "Warrenpoint",
    ],
    County.DUBLIN: [
        "Balbriggan",
        "Blanchardstown",
        "Clondalkin",
        "Donabate",
        "Dublin City",
        "Dún Laoghaire",
        "Howth",
        "Lucan",
        "Malahide",
        "Rush",
        "Skerries",
        "Swords",
        "Tallaght",
    ],
    County.FERMANAGH: [
        "Ballinamallard",
        "Belleek",
        "Derrygonnelly",
        "Enniskillen",
        "Irvinestown",
        "Kesh",
        "Lisnaskea",
        "Roslea",
    ],
    County.GALWAY: [
        "An Spidéal",
        "Athenry",
        "Ballinasloe",
        "Clifden",
        "Galway City",
        "Gort",
        "Loughrea",
        "Moycullen",
        "Oranmore",
        "Oughterard",
        "Portumna",
        "Tuam",
    ],
    County.KERRY: [
        "Ballybunion",
        "Cahersiveen",
        "Castleisland",
        "Dingle",
        "Kenmare",
        "Killarney",
        "Killorglin",
        "Listowel",
        "Milltown",
        "Tralee",
    ],
    County.KILDARE: [
        "Athy",
        "Celbridge",
        "Clane",
        "Kilcock",
        "Kildare Town",
        "Leixlip",
        "Maynooth",
        "Monasterevin",
        "Naas",
        "Newbridge",
        "Sallins",
    ],
    County.KILKENNY: [
        "Ballyragget",
        "Callan",
        "Castlecomer",
        "Graiguenamanagh",
        "Kilkenny City",
        "Mooncoin",
        "Thomastown",
    ],
    County.LAOIS: [
        "Abbeyleix",
        "Durrow",
        "Mountmellick",
        "Mountrath",
        "Portarlington",
        "Portlaoise",
        "Rathdowney",
        "Stradbally",
    ],
    County.LEITRIM: [
        "Ballinamore",
        "Carrick-on-Shannon",
        "Dromahair",
        "Drumshanbo",
        "Kinlough",
        "Manorhamilton",
        "Mohill",
    ],
    County.LIMERICK: [
        "Abbeyfeale",
        "Adare",
        "Askeaton",
        "Castleconnell",
        "Croom",
        "Kilmallock",
        "Limerick City",
        "Newcastle West",
        "Rathkeale",
    ],
    County.LONDONDERRY: [
        "Coleraine",
        "Derry / Londonderry",
        "Draperstown",
        "Dungiven",
        "Limavady",
        "Maghera",
        "Magherafelt",
        "Portstewart",
    ],
    County.LONGFORD: [
        "Ballymahon",
        "Drumlish",
        "Edgeworthstown",
        "Granard",
        "Lanesborough",
        "Longford Town",
    ],
    County.LOUTH: [
        "Ardee",
        "Blackrock",
        "Carlingford",
        "Drogheda",
        "Dundalk",
        "Dunleer",
        "Termonfeckin",
    ],
    County.MAYO: [
        "Ballina",
        "Ballinrobe",
        "Ballyhaunis",
        "Belmullet",
        "Castlebar",
        "Claremorris",
        "Foxford",
        "Louisburgh",
        "Swinford",
        "Westport",
    ],
    County.MEATH: [
        "Ashbourne",
        "Athboy",
        "Dunboyne",
        "Dunshaughlin",
        "Enfield",
        "Kells",
        "Laytown-Bettystown",
        "Navan",
        "Oldcastle",
        "Ratoath",
        "Slane",
        "Trim",
    ],
    County.MONAGHAN: [
        "Ballybay",
        "Carrickmacross",
        "Castleblayney",
        "Clones",
        "Emyvale",
        "Monaghan Town",
    ],
    County.OFFALY: [
        "Banagher",
        "Birr",
        "Clara",
        "Daingean",
        "Edenderry",
        "Ferbane",
        "Kilcormac",
        "Tullamore",
    ],
    County.ROSCOMMON: [
        "Athleague",
        "Ballaghaderreen",
        "Boyle",
        "Castlerea",
        "Elphin",
        "Roscommon Town",
        "Strokestown",
    ],
    County.SLIGO: [
        "Ballymote",
        "Collooney",
        "Enniscrone",
        "Grange",
        "Sligo Town",
        "Strandhill",
        "Tubbercurry",
    ],
    County.TIPPERARY: [
        "Cahir",
        "Carrick-on-Suir",
        "Cashel",
        "Clonmel",
        "Fethard",
        "Nenagh",
        "Roscrea",
        "Templemore",
        "Thurles",
        "Tipperary Town",
    ],
    County.TYRONE: [
        "Ballygawley",
        "Castlederg",
        "Coalisland",
        "Cookstown",
        "Dungannon",
        "Fintona",
        "Omagh",
        "Strabane",
    ],
    County.WATERFORD: [
        "Cappoquin",
        "Dungarvan",
        "Dunmore East",
        "Lismore",
        "Portlaw",
        "Tallow",
        "Tramore",
        "Waterford City",
    ],
    County.WESTMEATH: [
        "Athlone",
        "Castlepollard",
        "Delvin",
        "Kilbeggan",
        "Kinnegad",
        "Moate",
        "Mullingar",
        "Rochfortbridge",
    ],
    County.WEXFORD: [
        "Bunclody",
        "Courtown",
        "Enniscorthy",
        "Ferns",
        "Gorey",
        "New Ross",
        "Rosslare Harbour",
        "Wexford Town",
    ],
    County.WICKLOW: [
        "Arklow",
        "Aughrim",
        "Baltinglass",
        "Blessington",
        "Bray",
        "Enniskerry",
        "Greystones",
        "Kilcoole",
        "Newtownmountkennedy",
        "Rathdrum",
        "Tinahely",
        "Wicklow Town",
    ],
}


class Instrument(models.TextChoices):
    """Instruments commonly played at jam sessions, including Irish traditional."""

    ACCORDION = "accordion", _("Accordion")
    ACOUSTIC_GUITAR = "acoustic_guitar", _("Acoustic Guitar")
    BANJO = "banjo", _("Banjo")
    BASS_GUITAR = "bass_guitar", _("Bass Guitar")
    BODHRAN = "bodhran", _("Bodhrán")
    CELLO = "cello", _("Cello")
    CLARINET = "clarinet", _("Clarinet")
    DJ = "dj", _("DJ / Turntables")
    DOUBLE_BASS = "double_bass", _("Double Bass")
    DRUMS = "drums", _("Drums")
    ELECTRIC_GUITAR = "electric_guitar", _("Electric Guitar")
    FLUTE = "flute", _("Flute")
    HARMONICA = "harmonica", _("Harmonica")
    HARP = "harp", _("Harp")
    KEYBOARD = "keyboard", _("Keyboard / Synth")
    MANDOLIN = "mandolin", _("Mandolin")
    PERCUSSION = "percussion", _("Percussion")
    PIANO = "piano", _("Piano")
    SAXOPHONE = "saxophone", _("Saxophone")
    TIN_WHISTLE = "tin_whistle", _("Tin Whistle")
    TROMBONE = "trombone", _("Trombone")
    TRUMPET = "trumpet", _("Trumpet")
    UILLEANN_PIPES = "uilleann_pipes", _("Uilleann Pipes")
    UKULELE = "ukulele", _("Ukulele")
    VIOLIN = "violin", _("Violin / Fiddle")
    VOCALS = "vocals", _("Vocals")
    OTHER = "other", _("Other")


class MusicGenre(models.TextChoices):
    """Fixed list of music genres, kept in alphabetical order by label."""

    BLUES = "blues", _("Blues")
    BLUES_ROCK = "blues_rock", _("Blues Rock")
    CLASSICAL = "classical", _("Classical")
    COUNTRY = "country", _("Country")
    ELECTRONIC = "electronic", _("Electronic / Dance")
    FOLK = "folk", _("Folk")
    FUNK = "funk", _("Funk")
    GOSPEL = "gospel", _("Gospel")
    HIP_HOP = "hip_hop", _("Hip Hop / Rap")
    INDIE = "indie", _("Indie / Alternative")
    IRISH_TRADITIONAL = "irish_traditional", _("Irish Traditional")
    JAZZ = "jazz", _("Jazz")
    LATIN = "latin", _("Latin")
    METAL = "metal", _("Metal")
    POP = "pop", _("Pop")
    PROGRESSIVE_METAL = "progressive_metal", _("Progressive Metal")
    PROGRESSIVE_ROCK = "progressive_rock", _("Progressive Rock")
    PUNK = "punk", _("Punk")
    RNB_SOUL = "rnb_soul", _("R&B / Soul")
    REGGAE = "reggae", _("Reggae")
    ROCK = "rock", _("Rock")
    SINGER_SONGWRITER = "singer_songwriter", _("Singer-Songwriter")
    SKA = "ska", _("Ska")
    WORLD = "world", _("World Music")

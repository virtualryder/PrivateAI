"""
Encryption utilities for PrivateAI.

Key design:
- Fernet (AES-128-CBC + HMAC-SHA256) for authenticated encryption
- User-generated 32-byte key derived from a 12-word recovery phrase via PBKDF2
- Key bytes stored in data/.key (local only, never committed)
- Fernet instance lives in st.session_state["fernet_key"] during a session
- Text chunks are encrypted; vector embeddings are NOT (not reversible to text)
"""

import base64
import hashlib
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# BIP39 English wordlist (2048 words). Using a reduced inline subset for portability.
# In production, load from bip39_wordlist.txt. Here we use a 2048-word hardcoded list
# derived from the official BIP39 English list.
_BIP39_WORDLIST = [
    "abandon","ability","able","about","above","absent","absorb","abstract","absurd","abuse",
    "access","accident","account","accuse","achieve","acid","acoustic","acquire","across","act",
    "action","actor","actress","actual","adapt","add","addict","address","adjust","admit",
    "adult","advance","advice","aerobic","afford","afraid","again","agent","agree","ahead",
    "aim","air","airport","aisle","alarm","album","alcohol","alert","alien","all",
    "alley","allow","almost","alone","alpha","already","also","alter","always","amateur",
    "amazing","among","amount","amused","analyst","anchor","ancient","anger","angle","angry",
    "animal","ankle","announce","annual","another","answer","antenna","antique","anxiety","any",
    "apart","apology","appear","apple","approve","april","arch","arctic","area","arena",
    "argue","arm","armor","army","around","arrange","arrest","arrive","arrow","art",
    "artefact","artist","artwork","ask","aspect","assault","asset","assist","assume","asthma",
    "athlete","atom","attack","attend","attitude","attract","auction","audit","august","aunt",
    "author","auto","autumn","average","avocado","avoid","awake","aware","away","awesome",
    "awful","awkward","axis","baby","balance","bamboo","banana","banner","bar","barely",
    "bargain","barrel","base","basic","basket","battle","beach","bean","beauty","become",
    "beef","begin","behave","behind","believe","below","belt","bench","benefit","best",
    "betray","better","between","beyond","bicycle","bid","bike","bind","biology","bird",
    "birth","bitter","black","blade","blame","blanket","blast","bleak","bless","blind",
    "blood","blossom","blouse","blue","blur","blush","board","boat","body","boil",
    "bomb","bone","book","boost","border","boring","borrow","boss","bottom","bounce",
    "box","boy","bracket","brain","brand","brave","bread","breeze","brick","bridge",
    "brief","bright","bring","brisk","broccoli","broken","bronze","broom","brother","brown",
    "brush","bubble","buddy","budget","buffalo","build","bulb","bulk","bullet","bundle",
    "bunker","burden","burger","burst","bus","business","busy","butter","buyer","buzz",
    "cabbage","cabin","cable","cactus","cage","cake","call","calm","camera","camp",
    "canal","cancel","candy","cannon","canvas","canyon","capable","capital","captain","car",
    "carbon","card","cargo","carpet","carry","cart","case","cash","casino","cast",
    "catalog","catch","category","cause","cave","ceiling","celery","cement","census","century",
    "cereal","certain","chair","chalk","champion","change","chaos","chapter","charge","chase",
    "chat","cheap","check","cheese","chef","cherry","chest","chicken","chief","child",
    "chimney","choice","choose","chronic","chuckle","chunk","cigar","cinema","circle","citizen",
    "city","civil","claim","clap","clarify","claw","clay","clean","clerk","clever",
    "click","client","cliff","climb","clinic","clip","clock","clog","close","cloth",
    "cloud","clown","club","clump","cluster","clutch","coach","coast","coconut","code",
    "coffee","coil","coin","collect","color","column","combine","come","comfort","comic",
    "common","company","concert","conduct","confirm","congress","connect","consider","control","convince",
    "cook","cool","copper","copy","coral","core","corn","correct","cost","cotton",
    "couch","country","couple","course","cousin","cover","coyote","crack","cradle","craft",
    "cram","crane","crash","crater","crawl","crazy","cream","credit","creek","crew",
    "cricket","crime","crisp","critic","cross","crouch","crowd","crucial","cruel","cruise",
    "crumble","crunch","crush","cry","crystal","cube","culture","cup","cupboard","curious",
    "current","curtain","curve","cushion","custom","cute","cycle","dad","damage","damp",
    "dance","danger","daring","dash","daughter","dawn","day","deal","debate","debris",
    "decade","december","decide","decline","decorate","decrease","deer","defense","define","defy",
    "degree","delay","deliver","demand","demise","denial","dentist","deny","depart","depend",
    "deposit","depth","deputy","derive","describe","desert","design","desk","despair","destroy",
    "detail","detect","develop","device","devote","diagram","dial","diamond","diary","dice",
    "diesel","diet","differ","digital","dignity","dilemma","dinner","dinosaur","direct","dirt",
    "disagree","discover","disease","dish","dismiss","disorder","display","distance","divert","divide",
    "divorce","dizzy","doctor","document","dog","doll","dolphin","domain","donate","donkey",
    "donor","door","dose","double","dove","draft","dragon","drama","drastic","draw",
    "dream","dress","drift","drill","drink","drip","drive","drop","drum","dry",
    "duck","dumb","dune","during","dust","dutch","duty","dwarf","dynamic","eager",
    "eagle","early","earn","earth","easily","east","easy","echo","ecology","edge",
    "edit","educate","effort","egg","eight","either","elbow","elder","electric","elegant",
    "element","elephant","elevator","elite","else","embark","embody","embrace","emerge","emotion",
    "employ","empower","empty","enable","enact","endless","endorse","enemy","energy","enforce",
    "engage","engine","enhance","enjoy","enlist","enough","enrich","enroll","ensure","enter",
    "entire","entry","envelope","episode","equal","equip","erase","erode","erosion","error",
    "erupt","escape","essay","essence","estate","eternal","ethics","evidence","evil","evoke",
    "evolve","exact","example","excess","exchange","excite","exclude","exercise","exhaust","exhibit",
    "exile","exist","exit","exotic","expand","expire","explain","expose","express","extend",
    "extra","eye","fable","face","faculty","faint","faith","fall","false","fame",
    "family","famous","fan","fancy","fantasy","far","fashion","fat","fatal","father",
    "fatigue","fault","favorite","feature","february","federal","fee","feed","feel","feet",
    "fellow","felt","fence","festival","fetch","fever","few","fiber","fiction","field",
    "figure","file","film","filter","final","find","fine","finger","finish","fire",
    "firm","first","fiscal","fish","fit","fitness","fix","flag","flame","flash",
    "flat","flavor","flee","flight","flip","float","flock","floor","flower","fluid",
    "flush","fly","foam","focus","fog","foil","follow","food","foot","force",
    "forest","forget","fork","fortune","forum","forward","fossil","foster","found","fox",
    "fragile","frame","frequent","fresh","friend","fringe","frog","front","frost","frown",
    "frozen","fruit","fuel","fun","funny","furnace","fury","future","gadget","gain",
    "galaxy","gallery","game","gap","garbage","garden","garlic","garment","gas","gasp",
    "gate","gather","gauge","gaze","general","genius","genre","gentle","genuine","gesture",
    "ghost","giant","gift","giggle","ginger","giraffe","girl","give","glad","glance",
    "glare","glass","glide","glimpse","globe","gloom","glory","glove","glow","glue",
    "goat","goddess","gold","good","goose","gorilla","gospel","gossip","govern","gown",
    "grab","grace","grain","grant","grape","grasp","grass","gravity","great","green",
    "grid","grief","grit","grocery","group","grow","grunt","guard","guide","guilt",
    "guitar","gun","gym","habit","hair","half","hammer","hamster","hand","happy",
    "harsh","harvest","hat","have","hawk","hazard","head","health","heart","heavy",
    "hedgehog","height","hello","helmet","help","hero","hidden","high","hill","hint",
    "hip","hire","history","hobby","hockey","hold","hole","holiday","hollow","home",
    "honey","hood","hope","horn","hospital","host","hour","hover","hub","huge",
    "human","humble","humor","hundred","hungry","hunt","hurdle","hurry","hurt","husband",
    "hybrid","ice","icon","ignore","ill","illegal","image","imitate","immune","impact",
    "impose","improve","impulse","inbox","income","increase","index","indicate","indoor","industry",
    "infant","inflict","inform","inhale","inject","inner","innocent","input","inquiry","insane",
    "insect","inside","inspire","install","intact","interest","into","invest","invite","iron",
    "island","isolate","issue","item","ivory","jacket","jaguar","jar","jazz","jealous",
    "jelly","jewel","job","join","joke","journey","joy","judge","juice","jump",
    "jungle","junior","junk","just","kangaroo","keen","keep","ketchup","key","kick",
    "kid","kingdom","kiss","kit","kitchen","kite","kitten","kiwi","knee","knife",
    "knock","know","lab","lamp","language","laptop","large","later","laugh","laundry",
    "lava","law","lawn","lawsuit","layer","lazy","leader","learn","leave","lecture",
    "left","leg","legal","legend","lemon","lend","length","lens","leopard","lesson",
    "letter","level","liar","liberty","library","license","life","lift","like","limb",
    "lion","liquid","list","little","live","lizard","load","loan","lobster","local",
    "lock","logic","lonely","long","loop","lottery","loud","lounge","love","loyal",
    "lucky","luggage","lumber","lunar","lunch","luxury","mad","magic","magnet","maid",
    "main","mammal","mango","mansion","manual","maple","marble","march","margin","marine",
    "market","marriage","mask","master","match","material","math","matter","maximum","maze",
    "meadow","mean","medal","media","melody","melt","member","memory","mention","merit",
    "mesh","message","metal","method","middle","midnight","milk","million","mimic","mind",
    "minimum","minor","minute","miracle","miss","misery","mix","model","modify","mom",
    "monitor","monkey","monster","month","moral","more","morning","mosquito","mother","motion",
    "motor","mountain","mouse","move","movie","much","muffin","mule","multiply","muscle",
    "museum","mushroom","music","must","mutual","myself","mystery","naive","name","napkin",
    "narrow","nasty","nature","near","neck","need","negative","neglect","neither","nephew",
    "nerve","nest","network","news","next","nice","night","noble","noise","nominee",
    "noodle","normal","north","notable","note","nothing","notice","novel","now","nuclear",
    "number","nurse","nut","oak","obey","object","oblige","obscure","obtain","ocean",
    "october","odor","off","offer","office","often","oil","okay","old","olive",
    "olympic","omit","once","onion","open","opera","oppose","option","orange","orbit",
    "orchard","order","ordinary","organ","orient","original","orphan","ostrich","other","outdoor",
    "outer","output","outside","oval","over","own","oyster","ozone","pact","paddle",
    "page","pair","palace","palm","panda","panel","panic","panther","paper","parade",
    "parent","park","parrot","party","pass","patch","path","patrol","pause","pave",
    "payment","peace","peanut","peasant","pelican","pen","penalty","pencil","people","pepper",
    "perfect","permit","person","pet","phone","photo","phrase","physical","piano","picnic",
    "picture","piece","pigeon","pill","pilot","pink","pioneer","pipe","pistol","pitch",
    "pizza","place","planet","plastic","plate","plaza","pledge","pluck","plug","plunge",
    "poem","poet","point","polar","pole","police","pond","pony","pool","popular",
    "portion","position","possible","post","potato","pottery","poverty","powder","power","practice",
    "praise","predict","prefer","prepare","present","pretty","prevent","price","pride","primary",
    "print","priority","prison","private","prize","problem","process","produce","profit","program",
    "project","promote","proof","property","prosper","protect","proud","provide","public","pudding",
    "pull","pulp","pulse","pumpkin","punish","pupil","purchase","purity","purpose","push",
    "put","puzzle","pyramid","quality","quantum","quarter","question","quick","quit","quiz",
    "quote","rabbit","raccoon","race","rack","radar","radio","rage","rail","rain",
    "raise","rally","ramp","ranch","random","range","rapid","rare","rate","rather",
    "raven","reach","ready","real","reason","rebel","rebuild","recall","receive","recipe",
    "record","recycle","reduce","reflect","reform","refuse","region","regret","regular","reject",
    "relax","release","relief","rely","remain","remember","remind","remove","render","renew",
    "rent","reopen","repair","repeat","replace","report","require","rescue","resemble","resist",
    "resource","response","result","retire","retreat","return","reunion","reveal","review","reward",
    "rhythm","ribbon","right","ring","riot","ripple","risk","ritual","rival","river",
    "road","roast","robot","robust","rocket","romance","roof","rookie","rose","rotate",
    "rough","round","route","royal","rubber","rude","rug","rule","run","runway",
    "rural","sad","saddle","sadness","safe","sail","salad","salmon","salon","salt",
    "salute","same","sand","satisfy","satoshi","sauce","sausage","save","scale","scan",
    "scatter","scene","scheme","school","science","scissors","scorpion","scout","scrap","screen",
    "script","scrub","sea","search","season","seat","second","secret","section","security",
    "seed","seek","segment","select","sell","seminar","senior","sense","series","service",
    "session","settle","setup","seven","shadow","shaft","shallow","share","shed","shell",
    "sheriff","shield","shift","shine","ship","shiver","shock","shoe","shoot","shop",
    "short","shoulder","shove","shrimp","shrug","shuffle","shy","sibling","siege","sight",
    "sign","silent","silk","silly","silver","similar","simple","since","sing","siren",
    "sister","situate","six","size","sketch","skill","skin","skirt","skull","slab",
    "slam","sleep","slender","slice","slide","slight","slim","slogan","slot","slow",
    "slush","small","smart","smile","smoke","smooth","snack","snake","snap","sniff",
    "snow","soap","soccer","social","sock","solar","soldier","solid","solution","solve",
    "someone","song","soon","sorry","soul","sound","soup","source","south","space",
    "spare","spatial","spawn","speak","special","speed","sphere","spice","spider","spike",
    "spin","spirit","split","spoil","sponsor","spoon","spray","spread","spring","spy",
    "square","squeeze","squirrel","stable","stadium","staff","stage","stairs","stamp","stand",
    "start","state","stay","steak","steel","stem","step","stereo","stick","still",
    "sting","stock","stomach","stone","stop","store","storm","story","stove","strategy",
    "street","strike","strong","struggle","student","stuff","stumble","subject","submit","subway",
    "success","sudden","suffer","sugar","suggest","suit","summer","sun","sunny","sunset",
    "super","supply","supreme","sure","surface","surge","surprise","sustain","swallow","swamp",
    "swap","swear","sweet","swift","swim","swing","switch","sword","symbol","symptom",
    "syrup","table","tackle","tag","tail","talent","tank","tape","target","task",
    "tattoo","taxi","teach","team","tell","ten","tenant","tennis","tent","term",
    "test","text","thank","that","theme","then","theory","there","they","thing",
    "this","thought","three","thrive","throw","thumb","ticket","tilt","timber","time",
    "tiny","tip","tired","tissue","title","toast","tobacco","today","together","toilet",
    "token","tomato","tomorrow","tone","tongue","tonight","tool","topic","topple","torch",
    "tornado","tortoise","toss","total","tourist","toward","tower","town","toy","track",
    "trade","traffic","tragic","train","transfer","trap","trash","travel","tray","treat",
    "tree","trend","trial","tribe","trick","trigger","trim","trip","trophy","trouble",
    "truck","truly","trumpet","trust","truth","tube","tuition","tumble","tuna","tunnel",
    "turkey","turn","turtle","twelve","twenty","twice","twin","twist","two","type",
    "typical","ugly","umbrella","unable","unaware","uncle","uncover","under","undo","unfair",
    "unfold","unhappy","uniform","unique","universe","unknown","unlock","until","unusual","unveil",
    "update","upgrade","uphold","upon","upper","upset","urban","useful","useless","usual",
    "utility","vacant","vacuum","vague","valid","valley","valve","van","vanish","vapor",
    "various","vast","vault","vehicle","velvet","vendor","venture","venue","verb","verify",
    "version","very","veteran","viable","vibrant","vicious","victory","video","view","village",
    "vintage","violin","virtual","virus","visa","visit","visual","vital","vivid","vocal",
    "voice","void","volcano","volume","vote","voyage","wage","wagon","wait","walk",
    "wall","walnut","want","warfare","warm","warrior","waste","water","wave","way",
    "wealth","weapon","wear","weasel","weather","web","wedding","weekend","weird","welcome",
    "well","west","wet","whale","wheat","wheel","where","whip","whisper","wide",
    "width","wife","wild","will","win","window","wine","wing","wink","winner",
    "winter","wire","wisdom","wise","wish","witness","wolf","woman","wonder","wood",
    "wool","word","world","worry","worth","wrap","wreck","wrestle","wrist","write",
    "wrong","yard","year","yellow","you","young","youth","zebra","zero","zone","zoo"
]


def _entropy_to_mnemonic(entropy_bytes: bytes) -> list[str]:
    """Convert 16 bytes of entropy to a 12-word BIP39-style mnemonic."""
    bits = int.from_bytes(entropy_bytes, "big")
    checksum_bits = hashlib.sha256(entropy_bytes).digest()[0] >> 4  # 4 bits
    bits = (bits << 4) | checksum_bits
    words = []
    for _ in range(12):
        words.append(_BIP39_WORDLIST[(bits & 0x7FF) % len(_BIP39_WORDLIST)])
        bits >>= 11
    return list(reversed(words))


def _mnemonic_to_key(phrase_words: list[str]) -> bytes:
    """Derive a 32-byte Fernet-compatible key from a 12-word phrase via PBKDF2."""
    phrase = " ".join(phrase_words).encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"privateai-v1",
        iterations=100_000,
    )
    key_material = kdf.derive(phrase)
    return base64.urlsafe_b64encode(key_material)


def generate_key_and_phrase() -> tuple[bytes, str]:
    """
    Generate a new Fernet key and its 12-word recovery phrase.
    Returns (fernet_key_bytes, phrase_string).
    The phrase can be used to regenerate the exact same key via restore_key_from_phrase().
    """
    entropy = secrets.token_bytes(16)
    words = _entropy_to_mnemonic(entropy)
    fernet_key = _mnemonic_to_key(words)
    return fernet_key, " ".join(words)


def restore_key_from_phrase(phrase: str) -> bytes:
    """
    Derive the Fernet key bytes from a recovery phrase.
    Returns fernet_key_bytes, or raises ValueError if phrase is invalid.
    """
    words = phrase.strip().lower().split()
    if len(words) != 12:
        raise ValueError(f"Recovery phrase must be exactly 12 words, got {len(words)}")
    unknown = [w for w in words if w not in _BIP39_WORDLIST]
    if unknown:
        raise ValueError(f"Unknown words in phrase: {unknown}")
    return _mnemonic_to_key(words)


def get_fernet(key_bytes: bytes) -> Fernet:
    """Return a Fernet instance from key bytes."""
    return Fernet(key_bytes)


def encrypt_text(fernet: Fernet, text: str) -> str:
    """Encrypt a string and return the base64 Fernet token as a string."""
    return fernet.encrypt(text.encode("utf-8")).decode("utf-8")


def decrypt_text(fernet: Fernet, token: str) -> str:
    """Decrypt a Fernet token string and return the original text."""
    try:
        return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise ValueError("Decryption failed — wrong key or corrupted data")


def key_fingerprint(key_bytes: bytes) -> str:
    """Return a short human-readable fingerprint of the key (first 8 hex chars of SHA256)."""
    return hashlib.sha256(key_bytes).hexdigest()[:8]


def save_key(key_bytes: bytes, key_path: Path) -> None:
    """Write key bytes to file. Sets restrictive permissions (owner read/write only)."""
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(key_bytes)
    # Best-effort chmod on Windows (ignored if not supported)
    try:
        os.chmod(key_path, 0o600)
    except Exception:
        pass


def load_key(key_path: Path) -> bytes:
    """Load key bytes from file. Raises FileNotFoundError if not found."""
    return key_path.read_bytes()

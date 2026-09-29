import json, os
#!/usr/bin/env python3
"""Every clip's exact opening and closing words, chosen by reading the transcript.

10 Sept, after Kamay reviewed all 40. No boundary here comes from punctuation, a
silence gap, or any other proxy. Each entry names the sentence the clip OPENS on
and the sentence it CLOSES on, so the viewer never arrives mid-thought and never
leaves before the idea lands.
"""

# name, (approx region), opening words, closing words, hook
CUTS = {
"Why Millionaires": [
 # 27 Sept 2026. "Why Millionaires Love PROBLEMS" (18:10). Kamay's call: the four
 # lessons this shares with week 1 STAY IN - affiliates choose what to post, and
 # three tellings of one teaching in different words is more useful to them than one.
 # Ad wall: the testimonial from 17:35 to the end (Peter Saje, YWIYC) is never cut.
 ("YOUR-BIGGEST-DISASTER", (0, 32),
  "most people think that they can't achieve success", "it doesn't end it, it creates it",
  ["THE DAY IT FALLS APART", "IS THE DAY YOU START"]),
 ("MORE-PROBLEMS-THAN-YOU", (27, 122),
  "one of the biggest misconceptions that people have",
  "that the average person could never in a million years deal with",
  ["SUCCESSFUL PEOPLE HAVE MORE", "PROBLEMS THAN YOU DO"]),
 ("JOBS-WAS-FIRED", (150, 192),
  "steven jobs was fired", "apple would not be what it is today",
  ["APPLE EXISTS BECAUSE", "JOBS GOT FIRED"]),
 ("LOST-80-PERCENT", (183, 222),
  "you look at airbnb", "come out stronger than ever before",
  ["THEY LOST 80% AND", "CAME BACK STRONGER"]),
 ("SHE-WAS-LIVING-IN-HER-CAR", (236, 274),
  "she was living out of her car", "learned at the bottom",
  ["JK ROWLING WAS LIVING", "OUT OF HER CAR"]),
 ("THE-FOREST-FIRE", (265, 307),
  "i remember smokey the bear", "forest fire is a blessing",
  ["A FOREST FIRE", "IS A BLESSING"]),
 ("NOTHING-IS-DONE-TO-YOU", (300, 354),
  "successful people don't look at obstacles", "is the seed of a greater benefit",
  ["NOTHING IS BEING", "DONE TO YOU"]),
 ("NEVER-HAD-ADVERSITY", (358, 405),
  "people always come up to me", "a change in condition",
  ["I HAVE NEVER HAD", "ADVERSITY IN MY LIFE"]),
 ("THE-450-MILLION-BREAKUP", (396, 468),
  "i had a partner", "dollars on tv around the world",
  ["LOSING HIS BUSINESS", "MADE HIM $450 MILLION"]),
 ("BANNED-FOR-LIFE", (458, 570),
  "i got sued by the federal trade commission", "for 26 weeks in a row",
  ["BANNED FROM TV, SO HE", "WROTE A BESTSELLER"]),
 ("REACT-OR-RESPOND", (595, 642),
  "there's a big distinction between how rich people",
  "where the other person is going to attack mode",
  ["THE NUMBER ONE DIFFERENCE", "BETWEEN RICH AND BROKE"]),
 ("RUN-AT-THE-PROBLEM", (648, 702),
  "there's a word, confront", "something better is coming out",
  ["RUN AT THE PROBLEM,", "NOT AWAY FROM IT"]),
 ("THE-TEAM-THATS-LOSING", (710, 750),
  "we see this with athletes", "because they're attacking, attacking, attacking",
  ["THE TEAM THAT'S", "LOSING WINS"]),
 ("WINNERS-HATE-LOSING", (742, 795),
  "show me a good loser and i'll show you a loser",
  "into a gold mine",
  ["WINNERS", "HATE LOSING"]),
 ("REPLACE-THE-HABIT", (810, 862),
  "you have a habit of reacting instead of responding",
  "start to replace it with a different habit",
  ["YOU CAN'T DELETE A HABIT,", "ONLY REPLACE IT"]),
 ("LAUGH-NOW", (858, 928),
  "remember this phrase", "therefore you can look at it differently",
  ["LAUGH WHILE IT'S", "STILL A DISASTER"]),
 ("PAIN-NOT-SUFFERING", (952, 1002),
  "it's not overcoming adversity", "but you don't have to suffer",
  ["PAIN IS CERTAIN.", "SUFFERING IS OPTIONAL."]),
 ("TONS-OF-DIRT-FOR-GOLD", (993, 1058),
  "people move tons of dirt just to get a few ounces of gold",
  "that's the day that your success begins",
  ["THEY MOVE TONS OF DIRT", "FOR AN OUNCE OF GOLD"]),
],
"7 Months": [
 ("MIND-LIKE-GLASS", (28,130),
  "when you're in silence for seven months", "of pure beingness emanates",
  ["YOUR MIND IS A LAKE", "NOISE IS THE WIND"]),
 ("CONFRONT-IT-VANISHES", (210,300),
  "most people cannot be in the silence", "and that's when you're free",
  ["CONFRONT IT ONCE", "AND IT VANISHES"]),
 ("DISTRACTION-ISNT-THE-POINT", (630,682),
  "now people think", "that was the point",
  ["REMOVING DISTRACTION", "IS NOT THE ANSWER"]),
 ("NO-BUTTONS-LEFT", (668,745),
  "the key was", "confronting is the key",
  ["I CLEARED EVERY TRIGGER", "THEY HAD NOTHING LEFT"]),
 ("PAPER-TIGER", (914,1035),
  "listen if you were a kid", "learned your entire life",
  ["EVERYTHING IN YOUR HEAD", "IS A PAPER TIGER"]),
],
"Ancestral": [
 ("MONEY-IS-EVIL-INHERITED", (106,185),
  "if a person is trying to make money", "that's working against you",
  ["YOUR ANCESTORS DECIDED", "MONEY WAS EVIL"]),
 ("THOUSAND-POUNDS-OF-ROCKS", (252,292),
  "imagine walking up a hill", "or achieve what you want",
  ["WHY SUCCESS FEELS", "LIKE WALKING UPHILL"]),
 ("WHY-YOU-SABOTAGE-LOVE", (302,360),
  "maybe early in your life", "that you don't even know is there",
  ["WHY YOU SABOTAGE", "EVERY GOOD RELATIONSHIP"]),
 ("I-STUTTERED", (412,490),
  "but the biggest one", "the intention of what i'm saying",
  ["I STUTTERED", "AND COULDN'T FACE A ROOM"]),
 ("AN-ANCESTOR-DROWNED", (1057,1136),
  "my mom was afraid of water", "there was a counter-intention",
  ["SHE FEARED WATER", "AN ANCESTOR DROWNED"]),
 ("YOURE-A-MAGICIAN", (1170,1270),
  "since in the brotherhood i knew how to clear", "you have no more resistance",
  ["I CLEARED HER FEAR", "SHE CALLED ME A MAGICIAN"]),
 ("TWO-WAYS-TO-CLEAR", (1362,1466),
  "if you have counter intentions", "some of the counter intentions",
  ["TWO WAYS TO CLEAR", "WHAT IS BLOCKING YOU"]),
 ("BEAUTY-IS-A-FREQUENCY", (1462,1524),
  "there's an aesthetic wave", "the easier life is",
  ["BEAUTY IS A FREQUENCY", "IT CLEARS YOUR FIELD"]),
 ("THE-GLASSES", (1565,1636),
  "i remember not being able to see", "that you've never had before",
  ["I NEVER KNEW", "THE WORLD WASN'T BLURRY"]),
],
"Beyond Good": [
 ("WHY-WAIT-LAUGH-NOW", (22,68),
  "what you call adversity", "why wait laugh now",
  ["SOMEDAY YOU'LL LAUGH", "SO WHY WAIT"]),
 ("BREATH-OF-FIRE", (62,188),
  "i remember when i was being transferred", "because this is an experience",
  ["SHACKLED ON THE TARMAC", "IN A PAPER SUIT"]),
 ("WE-PAY-TO-FEEL-BAD", (298,385),
  "when we were kids we wanted adventure", "isn't that goofy",
  ["WE PAY MONEY", "TO FEEL TERRIBLE"]),
 ("LEARNED-AT-THE-BOTTOM", (408,452),
  "every thing i know at the top", "what happened to me was a blessing",
  ["EVERYTHING I KNOW AT THE TOP", "I LEARNED AT THE BOTTOM"]),
 ("THE-CHINESE-FARMER", (458,565),
  "if we look at the story of the chinese man", "there's just news",
  ["MAYBE IT'S BAD", "MAYBE IT'S NOT"]),
 ("VIKTOR-FRANKL", (556,648),
  "you may not see the blessings", "instead of just reacting to situations",
  ["HE COULDN'T CHANGE IT", "SO HE CHANGED HIS MIND"]),
],
"Every Millionaire": [
 ("THE-FIVE-YOU-WATCH", (110,208),
  "your income is going to be the average of the five people", "health wealth and happiness",
  ["YOUR INCOME IS THE AVERAGE", "OF WHO YOU WATCH"]),
 ("THEY-SENT-ME-TO-CADDY", (202,312),
  "listen my dad's a welder", "it became real",
  ["THEY SENT ME TO CADDY", "FOR RICH MEN"]),
 ("HANG-AROUND-BROKE-PEOPLE", (322,376),
  "look we knew this when we were kids", "possible",
  ["HANG AROUND BROKE PEOPLE", "YOU STAY BROKE"]),
 ("YOUR-ALGORITHM-TELLS", (370,416),
  "people always say", "telling you what you're thinking",
  ["YOUR YOUTUBE FEED", "EXPOSES YOUR INCOME"]),
 ("WHATS-IN-MY-FEED", (410,478),
  "someone was at my house the other day", "how you're thinking",
  ["LOOK AT WHAT", "MY OWN FEED RECOMMENDS"]),
 ("ONASSIS-BECAME-A-BUSBOY", (510,580),
  "if you listen to aristotle", "you start believing in yourself",
  ["HE LOST EVERYTHING", "AND BECAME A BUSBOY"]),
 ("THE-CLUB-SODA", (572,666),
  "i remember i was talking to josh and matt altman", "it works virtually 100% of the time",
  ["BROKE, THEY SAT", "IN BEVERLY HILLS BARS"]),
 ("TEN-YEARS-STILL-BROKE", (660,720),
  "now there is a side to this", "with deliberate intent",
  ["10 YEARS AROUND MONEY", "AND STILL BROKE"]),
 ("THE-BOSTON-ACCENT", (738,806),
  "i had a friend of mine", "of the people he's around",
  ["ONE SEMESTER SOUTH", "AND HIS ACCENT CHANGED"]),
 ("GET-RID-OF-YOUR-FRIENDS", (798,906),
  "listen to speakers who are very wealthy", "in their physical presence",
  ["THE HARD PART", "GET RID OF YOUR FRIENDS"]),
],
"If You Want": [
 ("SHARING-KILLS-THE-DREAM", (0,30),
  "the most dangerous thing a person can do", "actually kills it",
  ["SHARING YOUR DREAM", "DOESN'T FUEL IT. IT KILLS IT"]),
 ("EVEN-PEOPLE-WHO-LOVE-YOU", (30,110),
  "every single person wants you to fail", "better than they are",
  ["THEY LOVE YOU", "AND STILL WANT YOU TO FAIL"]),
 ("THE-MUSCLE-TEST", (130,210),
  "the brain is a receiver", "in such a massive way",
  ["ONE ROOM THINKING", "DROPPED HIS ARM"]),
 ("DONT-TELL-ANYONE", (204,246),
  "when you have a dream", "because they want you to fail",
  ["TELL NO ONE", "YOUR GOAL"]),
 ("PROTECT-THE-SEED", (332,388),
  "it's not telling people your dream", "which is ultimate success",
  ["A DREAM IS A SEED", "BIRDS EAT SEEDS"]),
 ("THEY-WANT-YOU-AT-THEIR-LEVEL", (408,455),
  "it's not that they want you to fail", "from achieving your goals",
  ["THEY DON'T WANT YOU TO FAIL", "THEY WANT YOU LEVEL WITH THEM"]),
 ("THE-MASTERMIND-EXCEPTION", (458,552),
  "there is an exception to this silence rule", "the exact same dream",
  ["THE ONE EXCEPTION", "TO TELLING NO ONE"]),
 ("THE-ROLLS-ROYCE", (602,664),
  "here's a perfect example", "that's the moment it begins to die",
  ["I WANTED IT FOR 4 YEARS", "AND TOLD NOBODY"]),
],
}


# Explicit end times, in SOURCE seconds, for the few places where no automatic
# rule can land it. 12 Sept: "There's just news." ends at 560.61 with only a
# 0.21s gap before "You may not see the blessings" - the trim loop pulled back,
# lost the anchor, and restored an end three seconds late.
END_OVERRIDE = {
    "THE-CHINESE-FARMER": 560.76,
}


# Freeze the picture at these clip-relative times - a new scene appears after
# them. Measured from the RENDERED clip, which is the only reliable detector.
VIS_OVERRIDE = {
    "MONEY-IS-EVIL-INHERITED": 73.267,
    "THE-CLUB-SODA": 85.733,
    "THE-MASTERMIND-EXCEPTION": 87.533,
    "VIKTOR-FRANKL": 81.267,
    "WE-PAY-TO-FEEL-BAD": 76.267
}

# ---------------------------------------------------------------------------
# PLANS AS JSON, 27 Sept 2026. A cut plan is data, not code: the cloud factory
# reads the same plan the Mac does, and a planning routine can write one without
# editing a Python file. Any plans/*.json next to this file (or in
# ~/Kamay/vsc-machine/plans) is merged in, keyed on its source prefix.
# ---------------------------------------------------------------------------
def _load_json_plans():
    import glob as _glob
    for _d in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "plans"),
               os.path.expanduser("~/Desktop/VSC/vsc-machine/plans")):
        for _f in sorted(_glob.glob(os.path.join(_d, "*.json"))):
            try:
                _p = json.load(open(_f))
            except Exception:
                continue
            _pre = _p.get("prefix")
            if not _pre or not _p.get("clips"):
                continue
            _cl = [(c["name"], tuple(c["region"]), c["open"], c["close"],
                    c["hook"] if len(c.get("hook", [])) != 1 else c["hook"][0])
                   for c in _p["clips"]]
            CUTS.setdefault(_pre, [])
            _have = {n for n, *_ in CUTS[_pre]}
            CUTS[_pre] += [c for c in _cl if c[0] not in _have]


_load_json_plans()

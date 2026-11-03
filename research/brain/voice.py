"""BFF Brain's voice: how Ask BFF talks. The answers themselves (numbers, verdicts, reasons) come from the page's own
functions; this file only decides how they are said, in Ben's voice: short, direct, a little playful, first person, the
verdict up front, never padding. train.py ships it inside brain.json, so the page needs nothing else.

Lines are picked by the answer's intent and mood (for example compare:close or trade:bad), varied by the question so the
same question gets the same opener, and never the same opener twice in a row. Closers are added to about half of the
answers so it does not read like a form letter. Honest by design: Ask BFF is a bot that Ben built and taught, and it says
so whenever someone asks whether they are talking to a person.
No outside AI is involved: everything here is plain text that the page assembles."""

OPEN = {
    # start / sit and keep / drop
    'compare:easy': ["Not even close.", "Easy one.", "I wouldn't overthink this one.", "This one's pretty clear to me.", "Don't sweat this one."],
    'compare:close': ["Ooh, tough one.", "Honestly? This is close.", "I went back and forth on this.", "Coin-flip territory, but I'll give you a lean.",
                      "Here's how I'd break the tie."],
    'compare:keep': ["Long-term question, so I'm looking at the rest of the season.", "Here's how I'd handle the roster spot.", "Rest of season is what matters here."],
    # trades
    'trade:good': ["I like this for you.", "This one tilts your way.", "If I'm you, I'm happy with this.", "Good deal for you, by my numbers."],
    'trade:bad': ["I'd pump the brakes here.", "Careful with this one.", "I wouldn't do this one as is.", "My numbers don't love this for you."],
    'trade:even': ["This one's pretty even.", "Honestly, both sides do fine here.", "Fair deal, so it comes down to what you need."],
    'trade_targets': ["Here's who I'd go after.", "If I'm shopping, these are my targets."],
    'tradevalue': ["Here's what he's worth to me.", "Here's how I'd value him."],
    # one player
    'player': ["Here's my read.", "Here's how I see it.", "Okay, here's the deal.", "Quick take:"],
    'injury:bad': ["Bad news, unfortunately.", "Ugh, not what you want to hear.", "Not great."],
    'injury:q': ["Here's where it stands.", "Keep an eye on this one.", "It's a wait-and-see situation."],
    'injury:good': ["Good news here.", "You're good.", "No worries on this one."],
    'stats': ["Here's what he's done.", "Pulled his numbers:", "Here's the stat sheet."],
    'ros': ["Big picture, here's his rest of season.", "Looking past this week:"],
    'who': ["Here's who he is.", "Quick intro:"],
    # lists
    'waiver': ["Here's who I'd be looking at.", "Waiver wire time.", "If I'm adding someone, it's from this group."],
    'rankings': ["Here's how I've got them.", "My rankings:", "Here's my board."],
    'sleepers': ["A few guys I like under the radar.", "Here are my sleepers."],
    'handcuff': ["Here's the handcuff picture.", "If you're protecting your guy, here's who to grab."],
    'picks': ["Here are my picks.", "Here's what I'm on."],
    'buysell': ["Here's where I'd buy and sell.", "Buy-low and sell-high time.", "Here's who I'd be buying and selling."],
    # games, teams, betting
    'game': ["Here's how I see this game.", "My take on this one:"],
    'team': ["Here's the rundown.", "Quick team report:"],
    'team_report': ["Here's how your team looks to me.", "Okay, I looked at your roster."],
    'team_lineup': ["Here's how I'd set it.", "Here's your lineup the way I'd play it."],
    'team_trades': ["Here are some deals I'd look at.", "I went shopping for you."],
    'team_waivers': ["Here's who I'd add for your team.", "These would help your roster."],
    'standings': ["Here's the table.", "Standings check:"],
    'defense': ["Here's who's giving up points.", "Matchup check:"],
    'sos': ["Schedule check:", "Here's who has it easy and who doesn't."],
    # props and betting: BFF predicts lines and shows chances; it makes no picks and builds no parlays (Nov 2026)
    'prop': ["Let's look at the number.", "Here's what BFF's numbers say."],
    'bets': ["No picks here, just BFF's numbers (21+ only).", "BFF doesn't make picks, but here's what the numbers say (21+ only):"],
    'parlay': ["BFF doesn't build parlays, but here's what it can tell you.", "No parlays from me, but here are the numbers you'd want:"],
    'td': ["Here's who's most likely to find the end zone.", "Touchdown chances:"],
    'weather': ["Weather check:"],
    # explaining
    'term': ["Good question.", "Quick explainer:", "Here's the short version."],
    'site': ["Good question.", "Here's how that works on the site."],
    'titles': ["History lesson:", "Here's the record book."],
    'sb_future': ["Here's how I see the title race."],
}

CLOSE = {
    'compare': ["Need upside or safety this week? Tell me and I'll rerun it by ceiling or floor.", "If you're the underdog this week, ask me for the ceiling play.",
                "Want a third option thrown in? Just add another name."],
    'trade': ["Type out your whole roster and I'll look for a better deal.", "Link your league and I'll show you what it does to your lineup.",
              "Want me to find a counter? Give me who else you'd move."],
    'player': ["Want him compared to someone? Give me two names.", "Ask me for his prop lines too, if you're into that."],
    'injury': ["Injury news updates on the site every 30 minutes, so check back closer to kickoff."],
    'waiver': ["Tell me your roster and I'll tell you who to drop for him.", "Ask me about any one of them and I'll go deeper."],
    'rankings': ["Ask about any guy on here and I'll tell you why he's there."],
    'stats': ["Want to know if it'll keep up? Ask me about his outlook."],
    'buysell': ["Ask me about any of them and I'll tell you what I'd offer."],
    'tradevalue': ["Want a fair deal built around him? Ask me for trade ideas.", "Thinking about moving him? Tell me who you'd want back and I'll check it."],
}

HELLO = ["Hey, it's Ben. Well, the bot version of me: I built this to answer the way I would, straight and with the numbers behind it.",
         "What's up! Ben here, or at least the bot I trained to talk football like me.",
         "Hey! Bot Ben here. Ask me whatever's on your mind about your team."]
THANKS = ["Anytime! Hit me up when the next one comes up.", "Of course. Good luck this week!", "Happy to help. Go win your matchup.",
          "No problem. I'm here all season."]
HOW = ["Doing good, just staring at the injury report like always. What do you need?", "Living the dream: football every Sunday. What can I help with?",
       "All good here. Got a lineup question for me?"]
WHO = ["I'm Ben's bot. Ben built BFF and taught me how he thinks about fantasy, so I talk like him, but I'm not a real person. "
       "Everything I tell you comes from BFF's own projections and data, and no outside chatbot sees your questions."]
JOKE = ["Why did the fantasy manager bring a ladder to the draft? He heard the values were going up. Okay, okay. Now ask me something useful about football.",
        "My lineup and my kicker have one thing in common: both are one bad week away from the waiver wire. Now, what football question can I help with?",
        "What do you call a running back who never fumbles? Fictional. Anyway, what football question can I help with?"]
VENT = ["Ugh, that one stings. Every season has a week like that.", "Rough. I've been there, believe me.", "Brutal week, I'm sorry. Let's fix it."]
VENT_GO = "Here's where I'd start to get it back on track:"
COMPLAINT = ["Fair. Projections miss sometimes, and I'd rather own it than pretend they don't.",
             "That's on the numbers, and I get the frustration. Here's how often they've been right, so you can judge for yourself."]
OFF = ["Ha, I'm strictly a football guy. Ask me about your lineup, a trade, waivers, a player, a team, the rules or how BFF works.",
       "That's outside my lane; I only do football. Try me on a start/sit, a trade or a player."]
UNKNOWN = ["Hmm, I didn't quite catch that.", "Not sure I follow, my bad."]
STATUS = "Ben's football brain · BFF's own model, no outside chatbot"
INTRO = ("<b>Hey, it's Ben.</b> Well, the bot version of me: I built BFF and taught this thing to answer like I would. Ask me anything "
         "football: who to start, whether a trade is fair, trade ideas for your team (just type your players), who to pick up, a player, a team, "
         "league leaders, the rules, or how any part of BFF works. Everything I say comes from BFF's own projections and data.")

BANK = {'open': OPEN, 'close': CLOSE, 'hello': HELLO, 'thanks': THANKS, 'how': HOW, 'who': WHO, 'joke': JOKE, 'vent': VENT, 'vent_go': VENT_GO,
        'complaint': COMPLAINT, 'off': OFF, 'unknown': UNKNOWN, 'status': STATUS, 'intro': INTRO, 'v': 1}

if __name__ == '__main__':
    n = sum(len(v) for v in OPEN.values()) + sum(len(v) for v in CLOSE.values())
    print('voice lines:', n, 'openers for', len(OPEN), 'intents/moods')

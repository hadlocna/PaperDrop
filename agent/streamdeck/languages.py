"""Offline spoken interface catalogue; English strings are stable message keys."""
import re
LANGUAGES = {'en':'English','fr':'Français','de':'Deutsch','it':'Italiano','pt':'Português'}
# Columns: English, French, German, Italian, European Portuguese.
DRAW_PROMPT = 'Tell me about the picture you want to make. Start talking when the button turns red.'
TALK_PROMPT = 'What would you like to tell your cousin? Start talking when the button turns red.'
ROWS = [
(DRAW_PROMPT, 'Décris le dessin que tu veux créer. Commence à parler quand le bouton devient rouge.', 'Erzähl mir, welches Bild du malen möchtest. Sprich los, wenn der Knopf rot wird.', 'Descrivi il disegno che vuoi creare. Inizia a parlare quando il pulsante diventa rosso.', 'Descreve o desenho que queres criar. Começa a falar quando o botão ficar vermelho.'),
(TALK_PROMPT, 'Que veux-tu raconter à ton cousin ou à ta cousine ? Commence à parler quand le bouton devient rouge.', 'Was möchtest du deinem Cousin oder deiner Cousine erzählen? Sprich los, wenn der Knopf rot wird.', 'Che cosa vuoi raccontare a tuo cugino o a tua cugina? Inizia a parlare quando il pulsante diventa rosso.', 'O que queres contar ao teu primo ou à tua prima? Começa a falar quando o botão ficar vermelho.'),
('Choose a house to send a postcard, or tap the pencil to draw and print.', 'Choisis une maison pour envoyer une carte, ou touche le crayon pour dessiner et imprimer.', 'Wähle ein Haus, um eine Karte zu schicken, oder tippe auf den Stift zum Malen und Drucken.', 'Scegli una casa per inviare una cartolina, oppure tocca la matita per disegnare e stampare.', 'Escolhe uma casa para enviar um postal, ou toca no lápis para desenhar e imprimir.'),
('Choose games, your language, or a postcard.', 'Choisis un jeu, ta langue ou une carte.', 'Wähle ein Spiel, deine Sprache oder eine Karte.', 'Scegli un gioco, la tua lingua o una cartolina.', 'Escolhe um jogo, a tua língua ou um postal.'),
('Choose your language.', 'Choisis ta langue.', 'Wähle deine Sprache.', 'Scegli la tua lingua.', 'Escolhe a tua língua.'),
('Your language is English. Let’s play!', 'Tu as choisi le français. On joue !', 'Du hast Deutsch gewählt. Lass uns spielen!', 'Hai scelto italiano. Giochiamo!', 'Escolheste português. Vamos brincar!'),
('Let’s play! Choose colors, letters, or numbers.', 'On joue ! Choisis les couleurs, les lettres ou les nombres.', 'Lass uns spielen! Wähle Farben, Buchstaben oder Zahlen.', 'Giochiamo! Scegli colori, lettere o numeri.', 'Vamos brincar! Escolhe cores, letras ou números.'),
('Tap the microphone to talk, or the picture to draw. Tap again when you are done.', 'Touche le micro pour parler, ou le dessin pour dessiner. Touche encore quand tu as terminé.', 'Tippe auf das Mikrofon zum Sprechen oder auf das Bild zum Malen. Tippe noch einmal, wenn du fertig bist.', 'Tocca il microfono per parlare o il disegno per disegnare. Tocca di nuovo quando hai finito.', 'Toca no microfone para falar, ou no desenho para desenhar. Toca outra vez quando acabares.'),
('No mail yet.', 'Pas encore de courrier.', 'Noch keine Post.', 'Non c’è ancora posta.', 'Ainda não tens correio.'),
('Here is your picture. Tap any button to go back.', 'Voici ton dessin. Touche un bouton pour revenir.', 'Hier ist dein Bild. Tippe auf eine Taste, um zurückzugehen.', 'Ecco il tuo disegno. Tocca un pulsante per tornare indietro.', 'Aqui está o teu desenho. Toca num botão para voltar.'),
('Tap any button to go back.', 'Touche un bouton pour revenir.', 'Tippe auf eine Taste, um zurückzugehen.', 'Tocca un pulsante per tornare indietro.', 'Toca num botão para voltar.'),
('Here is your picture. Tap any button to see the send button.', 'Voici ton dessin. Touche un bouton pour voir comment l’envoyer.', 'Hier ist dein Bild. Tippe auf eine Taste, um die Sendetaste zu sehen.', 'Ecco il tuo disegno. Tocca un pulsante per vedere come inviarlo.', 'Aqui está o teu desenho. Toca num botão para veres como enviar.'),
('Listen to your note, then press the green button to send.', 'Écoute ton message, puis touche le bouton vert pour l’envoyer.', 'Hör dir deine Nachricht an. Drücke dann die grüne Taste zum Senden.', 'Ascolta il tuo messaggio, poi premi il pulsante verde per inviarlo.', 'Ouve a tua mensagem e depois carrega no botão verde para enviar.'),
('I am making your picture. The buttons are resting.', 'Je prépare ton dessin. Les boutons se reposent.', 'Ich male dein Bild. Die Tasten machen eine Pause.', 'Sto creando il tuo disegno. I pulsanti si riposano.', 'Estou a fazer o teu desenho. Os botões estão a descansar.'),
('Oops. Please try again.', 'Oups ! Essaie encore.', 'Hoppla! Versuch es noch einmal.', 'Ops! Riprova.', 'Ups! Tenta outra vez.'),
('There is a postcard for you. Press play to listen, or the picture to see it.', 'Tu as reçu une carte ! Touche lecture pour écouter, ou le dessin pour le voir.', 'Du hast eine Karte bekommen! Drücke auf Wiedergabe zum Anhören oder auf das Bild zum Anschauen.', 'Hai ricevuto una cartolina! Premi ascolta per sentirla, o il disegno per guardarlo.', 'Tens um postal! Carrega para ouvir, ou toca no desenho para o veres.'),
('Your picture is ready. Sending it to the printer.', 'Ton dessin est prêt. Je l’envoie à l’imprimante.', 'Dein Bild ist fertig. Ich schicke es an den Drucker.', 'Il tuo disegno è pronto. Lo mando alla stampante.', 'O teu desenho está pronto. Vou enviá-lo para a impressora.'),
('Your picture has been sent to the printer.', 'Ton dessin a été envoyé à l’imprimante.', 'Dein Bild wurde an den Drucker geschickt.', 'Il tuo disegno è stato inviato alla stampante.', 'O teu desenho foi enviado para a impressora.'),
('Here is your picture. Press the green button to print, or the picture to look closer.', 'Voici ton dessin. Touche le bouton vert pour l’imprimer, ou le dessin pour le voir de plus près.', 'Hier ist dein Bild. Drücke die grüne Taste zum Drucken oder auf das Bild, um es größer zu sehen.', 'Ecco il tuo disegno. Premi il pulsante verde per stamparlo, o il disegno per vederlo meglio.', 'Aqui está o teu desenho. Carrega no botão verde para imprimir, ou no desenho para veres melhor.'),
('Your picture is on its way.', 'Ton dessin est en route.', 'Dein Bild ist unterwegs.', 'Il tuo disegno è in viaggio.', 'O teu desenho já vai a caminho.'),
('Your practice voice note is saved.', 'Ton message d’essai est enregistré.', 'Deine Übungsnachricht ist gespeichert.', 'Il tuo messaggio di prova è salvato.', 'A tua mensagem de teste está guardada.'),
('You earned a star!', 'Tu as gagné une étoile !', 'Du hast einen Stern gewonnen!', 'Hai guadagnato una stella!', 'Ganhaste uma estrela!'),
('Five stars! Amazing exploring. Tap play again for a new adventure.', 'Cinq étoiles ! Bravo ! Touche rejouer pour une nouvelle aventure.', 'Fünf Sterne! Toll gemacht! Tippe auf Noch einmal für ein neues Abenteuer.', 'Cinque stelle! Bravissimo! Tocca gioca ancora per una nuova avventura.', 'Cinco estrelas! Muito bem! Toca em jogar outra vez para uma nova aventura.'),
('Let us try another one. Listen carefully.', 'Essaie encore. Écoute bien.', 'Versuch es noch einmal. Hör gut zu.', 'Riprova. Ascolta bene.', 'Tenta outra vez. Ouve com atenção.'),
('Tap the red button when you are finished talking.', 'Touche le bouton rouge quand tu as fini de parler.', 'Tippe auf die rote Taste, wenn du fertig gesprochen hast.', 'Tocca il pulsante rosso quando hai finito di parlare.', 'Toca no botão vermelho quando acabares de falar.'),
]
CATALOG = {row[0]:dict(zip(LANGUAGES,row)) for row in ROWS}
TEMPLATES = {
'letter': ['Can you find the letter {x}?','Peux-tu trouver la lettre {x} ?','Findest du den Buchstaben {x}?','Trovi la lettera {x}?','Consegues encontrar a letra {x}?'],
'after': ['What number comes after {x}?','Quel nombre vient après {x} ?','Welche Zahl kommt nach {x}?','Quale numero viene dopo {x}?','Que número vem depois do {x}?'],
'plus': ['What is {x} plus {y}?','Combien font {x} plus {y} ?','Wie viel ist {x} plus {y}?','Quanto fa {x} più {y}?','Quanto é {x} mais {y}?'],
'color': ['Can you find {x}?','Peux-tu trouver le {x} ?','Findest du {x}?','Trovi il {x}?','Consegues encontrar o {x}?'],
'house': ['Who in {x}?','Qui à {x} ?','Wen in {x}?','Chi a {x}?','Quem em {x}?'],
}
COLORS = {'red':['red','rouge','Rot','rosso','vermelho'],'blue':['blue','bleu','Blau','blu','azul'],'green':['green','vert','Grün','verde','verde'],'yellow':['yellow','jaune','Gelb','giallo','amarelo'],'purple':['purple','violet','Lila','viola','roxo']}

def translate(text, language):
    if language not in LANGUAGES:raise ValueError('Unknown language')
    i=list(LANGUAGES).index(language)
    if text.startswith('Hello '):text='Choose games, your language, or a postcard.'
    if text.startswith('For ') and 'Tap the microphone' in text:text='Tap the microphone to talk, or the picture to draw. Tap again when you are done.'
    if text in CATALOG:return CATALOG[text][language]
    patterns=[('letter',r'Can you find the letter (\w)\?'),('after',r'What number comes after (\d+)\?'),('plus',r'What is (\d+) plus (\d+)\?'),('house',r'Who in (.+)\?'),('color',r'Can you find (red|blue|green|yellow|purple)\?')]
    for kind,pattern in patterns:
        match=re.fullmatch(pattern,text)
        if match:
            x=match[1]
            if kind=='color':x=COLORS[x][i]
            return TEMPLATES[kind][i].format(x=x,y=match[2] if len(match.groups())>1 else '')
    if language=='en':return text
    raise ValueError('Missing spoken translation')

def all_phrases():
    from games import voice_phrases
    return list(CATALOG)+voice_phrases()+['Who in Lisbon?','Who in Ohio?','Who in Düsseldorf?']

LABEL_ROWS = [
('Games','Jeux','Spiele','Giochi','Jogos'),('Home','Accueil','Start','Inizio','Início'),
('Back','Retour','Zurück','Indietro','Voltar'),('Draw & Print','Dessiner','Malen','Disegna','Desenhar'),
('Colors','Couleurs','Farben','Colori','Cores'),('Letters','Lettres','Buchstaben','Lettere','Letras'),('Numbers','Nombres','Zahlen','Numeri','Números'),
('Play again','Rejouer','Noch einmal','Gioca ancora','Jogar outra vez'),('Wonderful!','Bravo !','Wunderbar!','Bravissimo!','Muito bem!'),
('Talk','Parler','Sprechen','Parla','Falar'),('Draw','Dessiner','Malen','Disegna','Desenhar'),('Their mail','Courrier','Post','Posta','Correio'),
('Done','Terminé','Fertig','Finito','Acabei'),('Wait','Attends','Warten','Aspetta','Espera'),('Hold on','Attends','Warten','Aspetta','Espera'),
('Cancel','Annuler','Abbrechen','Annulla','Cancelar'),('Print here','Imprimer ici','Hier drucken','Stampa qui','Imprimir aqui'),
('Drawing','Dessin','Bild','Disegno','Desenho'),('Preview','Aperçu','Ansehen','Anteprima','Ver'),('Listen','Écouter','Anhören','Ascolta','Ouvir'),
('Redo','Refaire','Neu','Rifai','Refazer'),('Delete','Effacer','Löschen','Elimina','Apagar'),('Send','Envoyer','Senden','Invia','Enviar'),
('Picture','Dessin','Bild','Disegno','Desenho'),('Print','Imprimer','Drucken','Stampa','Imprimir'),('Return','Retour','Zurück','Indietro','Voltar'),
('Reply','Répondre','Antworten','Rispondi','Responder'),('Next','Suivant','Weiter','Avanti','Seguinte'),('Saved','Enregistré','Gespeichert','Salvato','Guardado'),
('Sent','Envoyé','Gesendet','Inviato','Enviado'),('Queued','En attente','Wartet','In attesa','Em espera'),('Printing','Impression','Druckt','In stampa','A imprimir'),
('Printed','Imprimé','Gedruckt','Stampato','Impresso'),('Checking','Vérification','Prüfen','Controllo','A verificar'),('Needs help','Besoin d’aide','Hilfe nötig','Serve aiuto','Precisa de ajuda'),
('Oops','Oups','Hoppla','Ops','Ups'),('Retry','Réessayer','Erneut','Riprova','Tentar'),
]
LABELS={row[0]:dict(zip(LANGUAGES,row)) for row in LABEL_ROWS}
def label(text, language):
    if text in LABELS:return LABELS[text][language]
    if text.lower() in COLORS:return COLORS[text.lower()][list(LANGUAGES).index(language)].capitalize()
    if text.startswith('Hear '):return dict(en='Hear',fr='Écouter',de='Hören',it='Ascolta',pt='Ouvir')[language]+' '+text[5:]
    return text

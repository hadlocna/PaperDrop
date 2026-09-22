"""Concrete, unambiguous riddles with picture answers, in all five languages."""
# English, French, German, Italian, European Portuguese.
ANSWERS = {
 'Cat': ('Cat', 'Chat', 'Katze', 'Gatto', 'Gato'),
 'Dog': ('Dog', 'Chien', 'Hund', 'Cane', 'Cão'),
 'Fish': ('Fish', 'Poisson', 'Fisch', 'Pesce', 'Peixe'),
 'Bird': ('Bird', 'Oiseau', 'Vogel', 'Uccello', 'Pássaro'),
 'Rabbit': ('Rabbit', 'Lapin', 'Kaninchen', 'Coniglio', 'Coelho'),
 'Flower': ('Flower', 'Fleur', 'Blume', 'Fiore', 'Flor'),
 'Star': ('Star', 'Étoile', 'Stern', 'Stella', 'Estrela'),
 'Pencil': ('Pencil', 'Crayon', 'Bleistift', 'Matita', 'Lápis'),
 'House': ('House', 'Maison', 'Haus', 'Casa', 'Casa'),
 'Square': ('Square', 'Carré', 'Quadrat', 'Quadrato', 'Quadrado'),
}
ANSWERS.update({
 'Clock': ('Clock','Horloge','Uhr','Orologio','Relógio'),
 'Comb': ('Comb','Peigne','Kamm','Pettine','Pente'),
 'Towel': ('Towel','Serviette','Handtuch','Asciugamano','Toalha'),
 'Umbrella': ('Umbrella','Parapluie','Regenschirm','Ombrello','Guarda-chuva'),
})
ICONS = {key: {'Flower':'Flower2','House':'Home'}.get(key,key) for key in ANSWERS}
RIDDLES = [
 ('Cat', ('I have whiskers and I say meow. What am I?', 'J’ai des moustaches et je fais miaou. Qui suis-je ?', 'Ich habe Schnurrhaare und sage miau. Wer bin ich?', 'Ho i baffi e faccio miao. Chi sono?', 'Tenho bigodes e faço miau. Quem sou eu?')),
 ('Dog', ('I wag my tail and I say woof. What am I?', 'Je remue la queue et je fais ouaf. Qui suis-je ?', 'Ich wedle mit dem Schwanz und sage wau. Wer bin ich?', 'Scodinzolo e faccio bau. Chi sono?', 'Abano a cauda e faço au-au. Quem sou eu?')),
 ('Fish', ('I have fins instead of feet and live underwater. What am I?', 'J’ai des nageoires au lieu de pieds et je vis sous l’eau. Qui suis-je ?', 'Ich habe Flossen statt Füßen und lebe unter Wasser. Wer bin ich?', 'Ho pinne invece di piedi e vivo sott’acqua. Chi sono?', 'Tenho barbatanas em vez de pés e vivo debaixo de água. Quem sou eu?')),
 ('Bird', ('I have feathers and a beak, and I build a nest. What am I?', 'J’ai des plumes et un bec, et je construis un nid. Qui suis-je ?', 'Ich habe Federn und einen Schnabel und baue ein Nest. Wer bin ich?', 'Ho piume e un becco e costruisco un nido. Chi sono?', 'Tenho penas e um bico e construo um ninho. Quem sou eu?')),
 ('Rabbit', ('I have long ears, soft fur, and I hop. What am I?', 'J’ai de longues oreilles, une fourrure douce et je bondis. Qui suis-je ?', 'Ich habe lange Ohren, weiches Fell und hüpfe. Wer bin ich?', 'Ho orecchie lunghe, pelo morbido e saltello. Chi sono?', 'Tenho orelhas compridas, pelo macio e dou saltinhos. Quem sou eu?')),
 ('Flower', ('I grow from a seed, open my petals, and welcome bees. What am I?', 'Je pousse à partir d’une graine, j’ouvre mes pétales et j’accueille les abeilles. Qui suis-je ?', 'Ich wachse aus einem Samen, öffne meine Blütenblätter und begrüße Bienen. Was bin ich?', 'Cresco da un seme, apro i petali e accolgo le api. Che cosa sono?', 'Cresço de uma semente, abro as pétalas e recebo as abelhas. O que sou eu?')),
 ('Star', ('Far away in the night sky, I twinkle like a tiny light. What am I?', 'Très loin dans le ciel de la nuit, je scintille comme une petite lumière. Qui suis-je ?', 'Weit weg am Nachthimmel funkle ich wie ein kleines Licht. Was bin ich?', 'Lontano nel cielo notturno brillo come una piccola luce. Che cosa sono?', 'Lá longe no céu da noite, cintilo como uma pequena luz. O que sou eu?')),
 ('Pencil', ('I get shorter as you use me to draw. You can sharpen my tip. What am I?', 'Je raccourcis quand tu dessines avec moi. Tu peux tailler ma pointe. Qui suis-je ?', 'Ich werde kürzer, wenn du mit mir malst. Du kannst meine Spitze anspitzen. Was bin ich?', 'Divento più corta quando mi usi per disegnare. Puoi temperare la mia punta. Che cosa sono?', 'Fico mais pequeno quando desenhas comigo. Podes afiar a minha ponta. O que sou eu?')),
 ('House', ('I have walls, windows, a roof, and a door for you to come home. What am I?', 'J’ai des murs, des fenêtres, un toit et une porte pour rentrer chez toi. Qui suis-je ?', 'Ich habe Wände, Fenster, ein Dach und eine Tür zum Heimkommen. Was bin ich?', 'Ho muri, finestre, un tetto e una porta per tornare a casa. Che cosa sono?', 'Tenho paredes, janelas, um telhado e uma porta para entrares em casa. O que sou eu?')),
 ('Square', ('I have four equal sides and four corners, like a little floor tile. What shape am I?', 'J’ai quatre côtés égaux et quatre coins, comme un petit carreau. Quelle forme suis-je ?', 'Ich habe vier gleich lange Seiten und vier Ecken, wie eine kleine Fliese. Welche Form bin ich?', 'Ho quattro lati uguali e quattro angoli, come una piastrella. Che forma sono?', 'Tenho quatro lados iguais e quatro cantos, como um azulejo. Que forma sou eu?')),
]

RIDDLES += [
 ('Clock', ('I have hands but cannot clap. I help you know when it is bedtime. What am I?', 'J’ai des aiguilles mais je ne couds pas. Je t’aide à savoir quand aller au lit. Qui suis-je ?', 'Ich habe Zeiger und zeige dir, wann Schlafenszeit ist. Was bin ich?', 'Ho lancette ma non pungo. Ti aiuto a sapere quando è ora di dormire. Che cosa sono?', 'Tenho ponteiros, mas não pico. Ajudo-te a saber quando é hora de dormir. O que sou eu?')),
 ('Comb', ('I have teeth but I never bite. I help tidy your hair. What am I?', 'J’ai des dents mais je ne mords jamais. Je t’aide à coiffer tes cheveux. Qui suis-je ?', 'Ich habe Zähne, beiße aber nie. Ich helfe dir, deine Haare zu ordnen. Was bin ich?', 'Ho denti ma non mordo mai. Ti aiuto a sistemare i capelli. Che cosa sono?', 'Tenho dentes, mas nunca mordo. Ajudo-te a arranjar o cabelo. O que sou eu?')),
 ('Towel', ('The more I dry you after a bath, the wetter I get. What am I?', 'Plus je te sèche après le bain, plus je suis mouillée. Qui suis-je ?', 'Je mehr ich dich nach dem Baden abtrockne, desto nasser werde ich. Was bin ich?', 'Più ti asciugo dopo il bagno, più mi bagno. Che cosa sono?', 'Quanto mais te seco depois do banho, mais molhada fico. O que sou eu?')),
 ('Umbrella', ('I open above your head when rain falls, but I am not a roof. What am I?', 'Je m’ouvre au-dessus de ta tête quand il pleut, mais je ne suis pas un toit. Qui suis-je ?', 'Ich öffne mich über deinem Kopf, wenn es regnet, bin aber kein Dach. Was bin ich?', 'Mi apro sopra la tua testa quando piove, ma non sono un tetto. Che cosa sono?', 'Abro-me por cima da tua cabeça quando chove, mas não sou um telhado. O que sou eu?')),
]

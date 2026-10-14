# Utiliser Azurik Dialogue Studio 1.0.0

## Lancer le logiciel et ouvrir le jeu

Décompressez toute la distribution, puis double-cliquez sur **`windows/Azurik Dialogue Studio.exe`**. Le logiciel s’ouvre dans sa propre fenêtre Windows ; il ne faut pas lancer une page web ou installer Python.

Si Windows signale l’absence de **Microsoft Edge WebView2 Runtime**, ce composant devra être installé avant de lancer l’application. L’application n’effectue aucune installation, aucun téléchargement payant ni aucun achat automatique.

Dans **Fichier**, choisissez :

- **Ouvrir un dump** : sélectionnez le dossier contenant le dossier `gamedata` du jeu extrait. Il contient notamment `english.xbr`, `French.xbr` et `German.xbr`.
- **Ouvrir une ISO** : sélectionnez votre ISO ou XISO Xbox européenne d’Azurik.

Les fichiers sont lus comme références originales. Les modifications restent dans votre projet jusqu’à l’export ; elles n’écrasent pas le dump ou l’ISO ouverts.

Le choix **Français / English** en haut change l’interface. Le choix **Langue du jeu** à gauche change la banque de ressources que vous modifiez. Une modification dans la banque française ne remplace pas automatiquement la ressource anglaise ou allemande.

## Modifier une boîte de dialogue

1. Ouvrez **Textes** et recherchez le nom du panneau.
2. Comparez **Panneau original** et **Votre aperçu**.
3. Écrivez votre texte dans **Texte de remplacement**. Le texte original est visible dans l’image ; il n’est pas transcrit automatiquement.
4. Réglez au besoin la police, la taille, la couleur et l’alignement dans l’inspecteur.
5. Cliquez sur **Actualiser l’aperçu**, puis **Appliquer le texte** pour enregistrer cette modification dans le projet.

Le remplacement garde le cadre et la zone de continuation d’origine. À l’export, les versions réduites de la texture sont régénérées avec le panneau. Réduisez la taille de police ou raccourcissez votre texte s’il ne tient pas dans la zone prévue.

La **Zone d’écriture** est un réglage avancé des limites du texte. Gardez-la dans la partie intérieure du panneau afin de conserver son décor et le bouton de continuation.

Cette opération remplace l’image d’une boîte déjà présente dans le jeu. Elle ne crée pas un nouvel événement ou une nouvelle conversation.

## Importer un texte ou remplacer un panneau

Sélectionnez la boîte dans **Textes**, puis cliquez sur **Importer un texte TXT**. Choisissez un fichier texte enregistré en **UTF-8** (avec ou sans BOM, jusqu’à 16 Ko). Son contenu remplace le texte du panneau et utilise les réglages de police et de zone sélectionnés. Les sauts de ligne Windows sont reconnus. L’export TXT conserve exactement votre texte, sans ajouter une ligne vide.

**Remplacer le panneau PNG** importe votre image complète, avec son cadre et son bouton de continuation. Le logiciel accepte les PNG statiques de moins de 16 Mo, jusqu’à 4096 × 4096 pixels. L’image est adaptée aux dimensions natives de la ressource et à sa compression, puis toutes ses versions réduites sont reconstruites. Une image haute résolution ne change donc pas la résolution du panneau Xbox d’origine.

Le texte d’un PNG n’est pas extrait automatiquement. Si vous tapez ensuite un nouveau texte et cliquez sur **Appliquer le texte**, ce texte remplace le PNG importé dans le cadre original du jeu. **Annuler** permet de retrouver votre PNG.

Ces imports sont immédiatement appliqués au projet ; vous pouvez les prévisualiser, les annuler et les rétablir. Le fichier TXT ou PNG source reste intact.

## Remplacer la voix d’un oracle

Dans **Voix**, choisissez la catégorie **Oracles**. Les identifiants de ressources restent ceux du jeu, même avec une interface française. Vous pouvez notamment rechercher :

| Recherche | Ressource originale correspondante |
|---|---|
| `w1_game_start` | Oracle associé au début de W1 |
| `w1_general` | Ressource d’oracle générale de W1 |
| `eld_a1_verb` | Ressource d’oracle d’A1 |
| `eld_d2_verb` | Ressource d’oracle de D2 |

La préécoute permet de confirmer la réplique avant de la remplacer. La banque française utilise des clés commençant par `loc/french/speech/eld_level_intros/` ; les banques anglaise et allemande ont leurs propres clés.

1. Sélectionnez la voix et cliquez sur **Charger la préécoute** pour écouter l’original.
2. Préparez votre propre enregistrement en **WAV PCM non compressé**. Les formats entiers 8, 16, 24 et 32 bits, mono et stéréo, sont acceptés.
3. Cliquez sur **Importer un enregistrement WAV**.
4. Utilisez **Écouter le remplacement** pour vérifier le résultat converti au format du jeu.

La fréquence et le nombre de canaux sont adaptés localement à ceux de la voix d’origine, puis le son est encodé au format natif de la ressource. La banque est reconstruite pour adapter sa ressource à la nouvelle durée, en gardant les références et les autres ressources.

Vous pouvez dépasser la durée originale ou utiliser une voix plus courte. Votre enregistrement est conservé entier : il n’est ni coupé ni accéléré. Une très courte fin silencieuse complète le dernier bloc Xbox, généralement quelques millisecondes. Les limites de cette version sont 10 minutes et 128 Mo par WAV. La durée affichée comme **Durée originale** est une référence, pas une limite d’importation.

## Volume et début de lecture

Après l’import WAV, réglez **Volume · gain en dB** (−12 à +12) puis cliquez sur **Appliquer les réglages audio**. Un gain positif utilise un limiteur de crête commun aux canaux pour augmenter le volume en contrôlant les pics. Vérifiez ensuite **Écouter le remplacement**.

**Début à lire · secondes** indique la partie initiale à retirer de l’enregistrement. Laissez **0** pour garder tout le fichier. Si votre voix comporte un silence avant la première phrase, choisissez précisément la fin de ce silence ; une valeur trop grande retire aussi la parole. Le réglage avance la première parole en supprimant cette portion, il n’ajoute pas de délai. Les fichiers importés restent intacts ; les réglages s’appliquent au remplacement encodé.

Le logiciel conserve le déclencheur de dialogue existant. La synchronisation exacte avec l’ouverture de la boîte reste à vérifier en jeu.

## Enregistrer les textes et les voix

**Exporter PNG** enregistre le panneau original ou le panneau avec votre modification.
Le texte du jeu étant une image, son original s’exporte en PNG. Votre texte rédigé
peut aussi être enregistré en UTF-8 avec **Exporter votre texte TXT**.

Dans **Voix**, **Exporter WAV** enregistre l’original ou le remplacement décodé
en WAV PCM, utilisable dans un logiciel audio. Choisissez un nouveau nom si le
fichier existe déjà ; les fichiers existants restent protégés.

Pour récupérer une bibliothèque, utilisez **Fichier → Exporter les panneaux**
ou **Exporter les voix**. Le logiciel crée un nouveau dossier pour la langue
active, trie les ressources selon leurs dossiers du jeu et écrit un catalogue.
Les modifications appliquées sont incluses. La progression de l’export des voix
reste visible pendant leur décodage.

## Exemple : remplacer la voix `training100-snd`

Choisissez **English** dans **Langue du jeu**, ouvrez **Voix**, puis recherchez
`training100-snd`. La ressource complète est
`loc/english/popups/training100-snd`. Importez votre WAV, écoutez le remplacement,
enregistrez le projet et construisez une nouvelle ISO.

Le jeu doit être réglé en **anglais** pour utiliser cette banque. La réplique
se déclenche dans le tutoriel lorsque l’événement existant est atteint.
Pour placer une réplique à un autre endroit, consultez [Événements](EVENTS.md).

Les MP3, les WAV à virgule flottante et les pistes des cinématiques Bink ne sont pas pris en charge dans cette version. Exportez un WAV PCM depuis votre outil d’enregistrement avant de l’importer. Le logiciel n’enregistre pas le microphone, ne fabrique pas de voix et ne clone pas une voix.

## Annuler et revenir aux originaux

| Raccourci ou commande | Action |
|---|---|
| **Ctrl+S** | Enregistrer le projet |
| **Ctrl+F** | Rechercher une ressource |
| **Ctrl+Z** | Annuler la dernière modification appliquée |
| **Ctrl+Maj+Z** | Rétablir une modification annulée |
| **Restaurer cet élément** | Retirer le remplacement du texte ou de la voix sélectionné |
| **Édition → Restaurer tous les originaux** | Retirer les modifications du projet courant |

Dans un champ de saisie, **Ctrl+Z** annule la frappe comme dans un éditeur de texte habituel. Les boutons **↶ / ↷** agissent sur les changements déjà appliqués au projet.

Restaurer les originaux retire vos modifications du projet ; cela ne réécrit pas une ISO que vous avez déjà exportée. Créez ensuite un nouvel export si vous souhaitez tester l’état restauré.

## Enregistrer et conserver un projet

**Enregistrer le projet** crée un fichier tel que `Mon-projet.azdialog.json`. Si vous avez importé des voix ou des panneaux PNG, un dossier voisin **`Mon-projet.azdialog.assets`** contient leurs WAV et PNG.

Gardez le fichier projet et son dossier de ressources importées ensemble, avec les mêmes noms. Le projet conserve les modifications, les réglages des panneaux et les empreintes des banques de jeu. Il ne contient pas une copie complète du jeu.

Pour reprendre le travail, choisissez **Fichier → Ouvrir un projet**. La copie source du jeu doit rester accessible et correspondre aux empreintes enregistrées.

Sur un autre ordinateur, copiez le projet et son dossier `.azdialog.assets` ensemble. Ouvrez d’abord **une copie identique du jeu**, puis ouvrez le projet déplacé. Si l’ancien chemin source n’existe plus, le logiciel utilise le jeu déjà ouvert seulement si toutes les empreintes des banques correspondent au projet. Une source différente est refusée ; déplacer le projet ne remplace pas les fichiers du jeu.

Gardez une copie de vos enregistrements personnels en dehors du logiciel. Ne publiez pas le dossier `.azdialog.assets` si vous ne souhaitez pas partager vos voix.

## Exporter les fichiers modifiés

**Exporter le mod** demande un **nouveau dossier**. Les banques modifiées y sont placées sous `gamedata`, avec :

- `iso-plan.json`, qui décrit les remplacements et leurs empreintes ;
- `dialogue-export.json`, qui récapitule les modifications exportées.

Les banques non modifiées ne sont pas recopiées comme remplacements. Les contrôles vérifient la source, la structure des ressources et les empreintes des fichiers produits. Un dossier d’export existant n’est pas écrasé.

## Construire une nouvelle ISO de test

1. Appliquez au moins un changement et enregistrez votre projet.
2. Choisissez **Fichier → Construire une nouvelle ISO**.
3. Sélectionnez une ISO source dont les banques correspondent au jeu ouvert dans votre projet.
4. Choisissez un **nouveau nom de fichier ISO** dans un dossier disposant d’assez d’espace libre.
5. Attendez la fin de la copie et de la vérification avant de fermer le logiciel.

La nouvelle image remplace seulement les banques de langue modifiées. L’exécutable Xbox, les niveaux, les cinématiques et les autres fichiers du disque restent conservés. L’ISO source n’est pas réécrite. La nouvelle image est relue, et les empreintes des fichiers sont vérifiées.

Cette ISO sert à votre test dans Xemu. La validation de sa structure et de ses fichiers ne garantit pas encore le fonctionnement de chaque dialogue en jeu : **les tests en jeu restent à réaliser**.

## Si Xemu montre encore l’ancienne version

EDIT : You need to clear the cache for the changes you make to take effect ! Don’t worry, this won’t affect your save files in any way!

Vérifiez d’abord que vous avez lancé **la nouvelle ISO** et que le jeu utilise la langue de la banque modifiée. Si l’ancienne ressource reste affichée, le cache du jeu Xbox peut conserver des données d’un disque précédent.

Azurik Dialogue Studio 1.0.0 n’a pas de bouton de nettoyage du cache et ne supprime aucun cache automatiquement. Un éventuel nettoyage doit viser uniquement les partitions de cache Xbox **X, Y et Z**, avec un outil adapté à votre installation. Les sauvegardes sont sur **E** : ne formatez pas cette partition et ne supprimez pas l’image du disque dur virtuel.

Le remplacement des banques dans une nouvelle ISO et un nettoyage limité aux caches Xbox n’effacent pas les sauvegardes.

## Sources et projets séparés

Ce logiciel fonctionne indépendamment d’Azurik Level Studio et d’Azurik-Decomp. Il ne modifie pas le projet de décompilation manuelle. Les logiciels sont distribuables ; les ISO, les banques originales du jeu, les voix extraites et les enregistrements importés restent des fichiers locaux à conserver séparément du dépôt public.

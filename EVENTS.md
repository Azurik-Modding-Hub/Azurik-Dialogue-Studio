# Déclencher un texte et une voix dans un niveau

Le principe est possible : **zone ou action → événement → panneau + voix**.
L’ajout d’un déclencheur exportable dans Level Studio reste à implémenter.
Dialogue Studio modifie actuellement les panneaux et sons déjà présents.

## Exemple concret : tutoriel

Le nœud natif `T1_helpnode` de `training_room.xbr` utilise la base
`loc/english/popups/training1`. Le contrôleur construit les noms de ses pages :

| Ressource | Première page |
|---|---|
| Image | `loc/english/popups/training100.tif` |
| Voix | `loc/english/popups/training100-snd` |

Un minuteur existant commande ce dialogue. Remplacer ces ressources conserve
ce déclenchement du tutoriel. Cela ne déplace pas la réplique vers un autre niveau.

## Exemple concret : miroirs pendant la journée

L’image `loc/english/popups/e6daylight00.tif` contient
« You can only operate the mirrors during daylight. ».
Sa voix associée est `loc/english/popups/e6daylight00-snd`.

Aucun déclencheur `helpnode` correspondant n’a été identifié dans le graphe E6
audité. La présence des ressources ne suffit donc pas à proposer un événement
exportable fiable. Cela ne démontre pas que le jeu ne peut jamais les appeler
par une autre logique.

## Ce que l’intégration à Level Studio devra gérer

1. Un emplacement dans le niveau et une condition, par exemple entrer dans une
   zone ou interagir avec un miroir pendant la nuit.
2. Un nœud de dialogue natif et ses connexions aux événements du niveau.
3. La base commune des panneaux et voix, les langues et les pages.
4. La répétition, l’activation unique et les conditions de progression.
5. La sauvegarde du graphe et des cellules du niveau, puis la vérification en jeu.

Des zones existantes reliées à des dialogues ont été identifiées dans W1.
Leur déplacement peut servir de point de départ aux essais ; leur création,
duplication et activation dans n’importe quel niveau demandent encore cette
intégration. Les collisions et le chargement des cellules doivent être vérifiés
avant de présenter ce fonctionnement comme utilisable.

Pour combiner les outils aujourd’hui, exportez les modifications du niveau dans
une ISO, puis utilisez cette ISO comme source de l’export de Dialogue Studio.
Les banques modifiées remplacent uniquement leurs fichiers de langue ; les
niveaux, cinématiques et l’exécutable de cette ISO restent conservés.

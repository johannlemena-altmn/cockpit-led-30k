# Plan 30 000 LED — Juin · mode d'emploi

## ⚠ Règle d'or
**On ne modifie JAMAIS un document d'origine ni le CRM live.** Ce dossier est un **espace de travail sur copies**.
- On alimente le dashboard avec un **export** (copie) du CRM.
- On ne reporte les changements dans Pixel/Betool/l'outil qu'**en fin de journée**, manuellement, et seulement si nécessaire.

## Contenu du dossier
| Fichier | À quoi ça sert |
|---|---|
| `Plan_30k_LED_Juin.xlsx` | **Le cockpit** : onglets DASHBOARD · PIPELINE · PARAMETRES |
| `Note_Plan_30k_LED.html` / `.pdf` | **La note 1 page** à présenter (boss puis équipe) + checklist contrôle v2 + messages de relance |
| `build_xlsx.py` | Le script qui régénère le classeur (utile si on veut faire évoluer la structure) |
| `README_mode_emploi.md` | Ce fichier |

## Mettre en route le dashboard (une fois)
1. Dans Pixel CRM / Betool, **exporter le pipeline** en CSV (tous les dossiers en cours).
2. Ouvrir `Plan_30k_LED_Juin.xlsx`, onglet **PIPELINE**, et **coller** les données à partir de la ligne 3 (1 ligne = 1 dossier). Colonnes calculées (ID, Âge, Priorité, Action) : **ne pas y toucher**, elles se remplissent seules.
3. Vérifier l'onglet **PARAMETRES** (objectif 30 000, cadence 1 500, dates de période, seuil de complétude pour déposer).

### Correspondance des colonnes (à mapper depuis l'export)
`Entreprise · SIRET · Secteur · Nb chantiers · Nb LED · Prime CEE · Surface · Date signature · % Pose réelle · Statut · Motif blocage · Responsable · Date dépôt`
Les colonnes **jaunes** = à saisir/maintenir à la main (surtout **% Pose réelle**, le nerf de la guerre).

## Le rituel quotidien (15 min)
**Chaque matin** — onglet DASHBOARD :
1. Lire le bandeau : *Déposé cumul · Reste à déposer · Rythme requis/j · Complétude moyenne*.
2. Lire le **TOP 12 à traiter aujourd'hui** (trié par priorité) → chacun prend ses dossiers.
3. Lire **BLOCAGES par motif** → envoyer les **relances pose** (messages dans la note) avant 10h.

**Chaque soir** :
4. Mettre à jour le **Statut** et le **% Pose** des dossiers traités (onglet PIPELINE).
5. Saisir les **« LED déposées du jour »** dans le tableau SUIVI QUOTIDIEN → le **burn-up** se recalcule.

## Statuts (menu déroulant)
`À contrôler → En contrôle → À corriger → Prêt à déposer → Déposé` (+ `Bloqué` avec un **motif**).
**Gate conformité** : un dossier ne passe **« Prêt à déposer »** que si **% Pose ≥ seuil** (PARAMETRES, défaut 100%). Sinon → `Bloqué / Attente pose client`.

## Note technique
- Le classeur s'ouvre et se recalcule normalement dans **Excel, Google Sheets ou Apple Numbers** (toutes les formules sont compatibles).
- Les **données d'amorçage** sont des **exemples anonymisés** : à remplacer par l'export réel du CRM.

"""Assistant « Nouvelle quête » : un seul formulaire qui crée le squelette jouable d'une quête.

Ce qu'il crée :
- la quête et ses récompenses ;
- le PNJ qui la donne (ou en réutilise un) et trois dialogues : proposer, attendre, recevoir le rapport ;
- la scène de l'objectif, à découvrir en explorant le lieu choisi (avec un combat si un monstre est choisi) ;
- trois marqueurs ``<quête>-en-cours``, ``<quête>-objectif``, ``<quête>-finie`` qui enchaînent le tout.

Les anciens dialogues du PNJ restent valables après la quête (les nouveaux passent devant).
"""
from django import forms
from django.db import transaction
from django.db.models import F

from ivakar_rpg.authoring import unique_slug
from ivakar_rpg.models import Choice, Item, Location, Monster, Npc, NpcDialogue, Outcome, Quest, Scene
from panel.ivakar_sections import _link_related_fields


class QuestWizardForm(forms.Form):
    # La quête
    title = forms.CharField(label="Titre de la quête", max_length=100)
    summary = forms.CharField(label="Résumé (journal du joueur)", widget=forms.Textarea(attrs={'rows': 2}),
                              required=False)
    objective = forms.CharField(label="Objectif affiché", max_length=200,
                                help_text="Ex. « Retrouver la bague perdue près du vieux moulin ».")
    # Qui la donne
    npc = forms.ModelChoiceField(label="PNJ qui la donne", queryset=Npc.objects.all(), required=False,
                                 help_text="Ou crée-le juste en dessous.")
    new_npc_name = forms.CharField(label="… ou nouveau PNJ : nom", max_length=60, required=False)
    new_npc_role = forms.CharField(label="Rôle du nouveau PNJ", max_length=60, required=False)
    giver_location = forms.ModelChoiceField(label="Où trouver ce PNJ", queryset=Location.objects.all(),
                                            required=False, help_text="Obligatoire pour un nouveau PNJ.")
    offer_text = forms.CharField(label="Ce qu'il dit pour proposer la quête (BBCode)",
                                 widget=forms.Textarea(attrs={'rows': 4}))
    accept_label = forms.CharField(label="Bouton pour accepter", max_length=100, initial="Accepter la mission")
    # L'objectif
    objective_location = forms.ModelChoiceField(label="Lieu de l'objectif", queryset=Location.objects.all())
    objective_title = forms.CharField(label="Titre de la scène de l'objectif", max_length=100)
    objective_text = forms.CharField(label="Texte de la scène de l'objectif (BBCode)",
                                     widget=forms.Textarea(attrs={'rows': 4}))
    objective_action = forms.CharField(label="Bouton pour accomplir l'objectif", max_length=100,
                                       initial="Passer à l'action")
    monster = forms.ModelChoiceField(label="Combat à remporter (facultatif)", queryset=Monster.objects.all(),
                                     required=False)
    # Le retour
    return_text = forms.CharField(label="Ce que dit le PNJ au retour (BBCode)", widget=forms.Textarea(attrs={'rows': 3}))
    reward_xp = forms.IntegerField(label="XP", min_value=0, initial=30)
    reward_coins = forms.IntegerField(label="Écus", min_value=0, initial=20)
    reward_item = forms.ModelChoiceField(label="Objet en récompense", queryset=Item.objects.all(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _link_related_fields(self)

    def clean(self):
        data = super().clean()
        if not data.get('npc') and not data.get('new_npc_name'):
            self.add_error('npc', "Choisis un PNJ ou donne le nom d'un nouveau PNJ.")
        if data.get('new_npc_name') and not data.get('giver_location'):
            self.add_error('giver_location', "Indique où trouver le nouveau PNJ.")
        return data


def _choice(scene, label, order=1, **outcome):
    choice = Choice.objects.create(scene=scene, label=label, order=order)
    Outcome.objects.create(choice=choice, result=Outcome.RESULT_SUCCESS, **outcome)
    return choice


@transaction.atomic
def build_quest(data):
    """Crée la quête et tout ce qui la rend jouable. Renvoie ``(quête, pnj, lieu du pnj)``."""
    quest = Quest.objects.create(
        slug=unique_slug(Quest, data['title']), title=data['title'], summary=data.get('summary', ''),
        objective=data['objective'], reward_xp=data['reward_xp'], reward_coins=data['reward_coins'],
        reward_item=data.get('reward_item'),
    )
    started, done_objective, finished = (f"{quest.slug}-en-cours"[:60], f"{quest.slug}-objectif"[:60],
                                         f"{quest.slug}-finie"[:60])

    npc = data.get('npc')
    location = data.get('giver_location')
    if npc is None:
        npc = Npc.objects.create(slug=unique_slug(Npc, data['new_npc_name']), name=data['new_npc_name'],
                                 role=data.get('new_npc_role', ''))
    if location is not None and not npc.locations.filter(pk=location.pk).exists():
        npc.locations.add(location)
    location = location or npc.locations.first()

    def scene(title, text, **fields):
        return Scene.objects.create(title=title[:100], slug=unique_slug(Scene, title, 80), text=text, **fields)

    offer = scene(f"{quest.title} : la demande", data['offer_text'], location=location, npc=npc)
    _choice(offer, data['accept_label'], 1, set_flag=started, start_quest=quest,
            text="Tu acceptes. Il te reste à agir.")
    _choice(offer, "Plus tard", 9)

    waiting = scene(f"{quest.title} : en attente", f"« Alors, où en es-tu ? {quest.objective} »",
                    location=location, npc=npc)
    _choice(waiting, "Je m'en occupe", 1)

    report = scene(f"{quest.title} : le rapport", data['return_text'], location=location, npc=npc)
    _choice(report, "Faire ton rapport", 1, set_flag=finished, complete_quest=quest)

    goal = scene(data['objective_title'], data['objective_text'], location=data['objective_location'],
                 explore_weight=2, required_flag=started, forbidden_flag=done_objective)
    if data.get('monster'):
        after = scene(f"{data['objective_title']} : après le combat",
                      "Le silence retombe. Ce que tu étais venu faire est accompli.")
        _choice(after, "Retourner faire ton rapport", 1, set_flag=done_objective)
        _choice(goal, data['objective_action'], 1, combat=data['monster'], next_scene=after)
    else:
        _choice(goal, data['objective_action'], 1, set_flag=done_objective, text="C'est fait.")
    _choice(goal, "Revenir plus tard", 9)

    # Les nouveaux dialogues passent devant les anciens, qui restent valables une fois la quête finie.
    NpcDialogue.objects.filter(npc=npc).update(order=F('order') + 3)
    NpcDialogue.objects.create(npc=npc, scene=report, order=1, required_flag=done_objective, forbidden_flag=finished)
    NpcDialogue.objects.create(npc=npc, scene=waiting, order=2, required_flag=started, forbidden_flag=done_objective)
    NpcDialogue.objects.create(npc=npc, scene=offer, order=3, forbidden_flag=started)
    return quest, npc, location

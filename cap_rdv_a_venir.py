#!/usr/bin/env python3
"""
Script de cap: garantit au plus 7 RDV 'a_venir' par commercial (toutes dates confondues).
Supprime les plus lointains d'abord, en gardant les plus proches.
"""

import os
import django
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm_visites.settings')
django.setup()

from front.models import Rendezvous, Commercial


def cap_rdv_a_venir(max_par_commercial: int = 7) -> None:
    commerciaux = Commercial.objects.filter(role='commercial')
    for com in commerciaux:
        qs = Rendezvous.objects.filter(commercial=com, statut_rdv='a_venir').order_by('date_rdv', 'heure_rdv')
        total = qs.count()
        if total <= max_par_commercial:
            continue
        # Garder les plus proches (début de queryset), supprimer le surplus (les plus lointains)
        a_supprimer = qs[max_par_commercial:]
        print(f"Commercial {com.prenom} {com.nom}: {total} -> {max_par_commercial} (suppression {a_supprimer.count()})")
        for rdv in a_supprimer:
            print(f"  - delete {rdv.date_rdv} {rdv.heure_rdv} {rdv.client.rs_nom if rdv.client else ''}")
            rdv.delete()


if __name__ == '__main__':
    cap_rdv_a_venir(7)

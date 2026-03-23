from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import DiaryImage


class Command(BaseCommand):
    help = (
        "Repara caminhos de imagens do diário que ficaram sem diretório "
        "(ex.: apenas 'foto.jpg' em vez de 'diary_images/.../foto.jpg')."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica correções no banco. Sem esta flag, roda apenas simulação.",
        )

    def handle(self, *args, **options):
        apply_changes = bool(options.get("apply"))
        media_root = Path(settings.MEDIA_ROOT)
        diary_images_root = media_root / "diary_images"

        if not diary_images_root.exists():
            self.stdout.write(self.style.WARNING("Pasta media/diary_images não encontrada."))
            return

        # Indexa arquivos existentes por basename para tentar relink.
        candidates_by_name = {}
        for p in diary_images_root.rglob("*"):
            if p.is_file():
                candidates_by_name.setdefault(p.name, []).append(p)

        total = 0
        missing = 0
        fixed = 0
        unresolved = 0

        qs = DiaryImage.objects.select_related("diary").all().order_by("id")
        for img in qs:
            total += 1
            image_name = getattr(img.image, "name", None)
            if not image_name:
                continue

            # Se já está válido, pula.
            try:
                if img.image.storage.exists(image_name):
                    continue
            except Exception:
                pass

            missing += 1
            basename = Path(str(image_name)).name
            candidates = candidates_by_name.get(basename, [])
            if not candidates:
                unresolved += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"[sem-candidato] id={img.id} diary={img.diary_id} file={image_name}"
                    )
                )
                continue

            # Heurística:
            # 1) Preferir candidato que contenha o dia do diário no caminho;
            # 2) Caso contrário, usar o mais recentemente modificado.
            target = None
            diary_date = getattr(img.diary, "date", None)
            if diary_date:
                y = f"{diary_date.year:04d}"
                m = f"{diary_date.month:02d}"
                d = f"{diary_date.day:02d}"
                for cand in candidates:
                    rel = str(cand.relative_to(media_root)).replace("\\", "/")
                    if f"/{y}/{m}/{d}/" in f"/{rel}/":
                        target = cand
                        break
            if target is None:
                target = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]

            new_rel = str(target.relative_to(media_root)).replace("\\", "/")
            self.stdout.write(
                f"[relink] id={img.id} diary={img.diary_id} old={image_name} -> new={new_rel}"
            )
            if apply_changes:
                DiaryImage.objects.filter(pk=img.pk).update(image=new_rel)
            fixed += 1

        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Modo: {mode}"))
        self.stdout.write(
            f"Total={total} | Com arquivo ausente={missing} | Relink possível={fixed} | Sem candidato={unresolved}"
        )


from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_vm_bootstrap_defaults_to_private_services_and_validates_sshd():
    script = (ROOT / "scripts/vm230-bootstrap.sh").read_text(encoding="utf-8")

    assert 'VM_HOSTNAME="${VM_HOSTNAME:-$(hostname)}"' in script
    assert 'EXPOSE_DEMO_PORTS="${EXPOSE_DEMO_PORTS:-0}"' in script
    assert 'ENABLE_SING_BOX_REDIRECT="${ENABLE_SING_BOX_REDIRECT:-0}"' in script
    assert 'if [[ "$EXPOSE_DEMO_PORTS" == "1" ]]' in script
    assert 'if [[ "$ENABLE_SING_BOX_REDIRECT" == "1" ]]' in script
    assert "sudo usermod -aG docker ubuntu" not in script
    assert "/etc/ssh/sshd_config.d/99-thin-signals.conf" in script
    assert "sudo sshd -t" in script


def test_home_vm_runtime_overrides_keep_services_private_and_recoverable():
    drop_in = (ROOT / "deploy/systemd/thin-signals-api-home-vm.conf").read_text(encoding="utf-8")
    egress_unit = (ROOT / "deploy/systemd/agi-sing-box.service").read_text(encoding="utf-8")
    env = (ROOT / "deploy/env/home-vm.env.example").read_text(encoding="utf-8")

    assert "Environment=TS_PROFILE=home-vm" in drop_in
    assert "Environment=TS_SEARXNG_URL=" in drop_in
    assert "StateDirectory=agi-sing-box" in egress_unit
    assert "After=network-online.target docker.service" in egress_unit
    assert "TS_PROFILE=home-vm" in env
    assert "TS_SEARXNG_URL=" in env
    assert "TS_OPENROUTER_KEY_FILE=.secrets/openrouter_key" in env


def test_searxng_pins_are_one_audited_immutable_build():
    tag = "2026.10.13-22c64b8d3"
    digest = "sha256:70f100d04af1ac841d59ffc1b6354e9e264c161ae47d5251be4e598013386065"
    expected = f"searxng/searxng:{tag}@{digest}"

    laptop = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    production = yaml.safe_load(
        (ROOT / "deploy/research/compose.yaml").read_text(encoding="utf-8")
    )
    installer = (ROOT / "scripts/vm232-research-contour.sh").read_text(encoding="utf-8")

    assert laptop["services"]["searxng"]["image"] == expected
    assert production["services"]["searxng"]["image"] == expected
    assert f'SEARX_IMAGE="{expected}"' in installer


def test_quickstart_compose_is_complete_private_and_secret_file_only():
    compose = yaml.safe_load((ROOT / "compose.quickstart.yaml").read_text(encoding="utf-8"))

    assert set(compose["services"]) == {
        "bootstrap", "pg", "migrate", "api", "ui", "searxng", "gpt-researcher",
    }
    assert compose["services"]["pg"]["image"].startswith(
        "pgvector/pgvector:pg16@sha256:"
    )
    assert compose["services"]["searxng"]["image"].startswith(
        "searxng/searxng:2026.10.13-22c64b8d3@sha256:"
    )
    assert compose["services"]["gpt-researcher"]["image"] == (
        "thin-signals/gpt-researcher:3.7.0-0957c301"
    )
    assert compose["services"]["migrate"]["command"] == ["alembic", "upgrade", "head"]
    assert compose["services"]["api"]["depends_on"]["migrate"]["condition"] == (
        "service_completed_successfully"
    )
    assert compose["services"]["migrate"]["depends_on"]["bootstrap"]["condition"] == (
        "service_completed_successfully"
    )
    for service in ("pg", "api", "ui", "searxng", "gpt-researcher"):
        for published in compose["services"][service].get("ports", []):
            assert "127.0.0.1" in str(published) or "TS_BIND_HOST" in str(published)
    rendered = (ROOT / "compose.quickstart.yaml").read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD=" not in rendered
    assert 'OPENROUTER_API_KEY="$$(cat /run/private/gptr_openrouter_key)"' in rendered
    assert "sk-or-" not in rendered
    assert "/run/secrets/pg_password" in rendered
    assert "/run/secrets/openrouter_key" in rendered
    assert "/run/private/openrouter_key" in rendered


def test_quickstart_builder_pins_upstream_and_never_deletes_volumes():
    script = (ROOT / "scripts/docker-quickstart.sh").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "0957c301ed06c2a5857b834358c7227c739041d4" in script
    assert 'GPTR_TAG="v3.7.0"' in script
    assert '"refs/tags/$GPTR_TAG:refs/tags/$GPTR_TAG"' in script
    assert "down -v" not in script
    assert "python:3.14.4-slim-bookworm@sha256:" in dockerfile
    assert "libgnutls30=3.7.9-2+deb12u7" in dockerfile
    assert "libssl3=3.0.22-1~deb12u1" in dockerfile
    assert "perl-base=5.36.0-7+deb12u4" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert (ROOT / "deploy/docker/requirements.lock").is_file()
    assert (ROOT / "deploy/docker/runtime.env.example").is_file()
    assert (ROOT / "docs/ops/DOCKER_QUICKSTART.md").is_file()


def test_home_vm_review_activation_is_explicit_bounded_and_keeps_stable_rules():
    drop_in = (
        ROOT / "deploy/systemd/thin-signals-api-review-enabled.conf"
    ).read_text(encoding="utf-8")

    assert "Environment=TS_RULES_VERSION=rules-0.1" in drop_in
    assert "Environment=TS_GPT_RESEARCHER_ENABLED=true" in drop_in
    assert "Environment=TS_GPT_RESEARCHER_URL=http://127.0.0.1:28000" in drop_in
    assert "Environment=TS_GPT_RESEARCHER_MAX_COST_USD=0.08" in drop_in
    assert "Environment=TS_ADVERSARIAL_REVIEW_ENABLED=true" in drop_in
    assert "Environment=TS_REVIEW_TIME_SECONDS=45" in drop_in
    assert "Environment=TS_REVIEW_MAX_COST_USD=0.03" in drop_in

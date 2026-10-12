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
    tag = "2026.10.11-ad46ebd7d"
    digest = "sha256:00ad29bb7d72d896ac3b3ff8b252d9ad9939da3e014828934363c61dba9b7e09"
    expected = f"searxng/searxng:{tag}@{digest}"

    laptop = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    production = yaml.safe_load(
        (ROOT / "deploy/research/compose.yaml").read_text(encoding="utf-8")
    )
    installer = (ROOT / "scripts/vm232-research-contour.sh").read_text(encoding="utf-8")

    assert laptop["services"]["searxng"]["image"] == expected
    assert production["services"]["searxng"]["image"] == expected
    assert f'SEARX_IMAGE="{expected}"' in installer

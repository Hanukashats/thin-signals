from pathlib import Path

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

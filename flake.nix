# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

{
  description = "Toolchain for the mindclade github-config repository";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs =
    { nixpkgs, ... }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
        "x86_64-darwin"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      perSystem =
        system:
        let
          pkgs = import nixpkgs {
            inherit system;
            config.allowUnfreePredicate = package: nixpkgs.lib.getName package == "terraform";
          };

          # Install the exact HashiCorp release used by CI and .terraform-version. The hashes
          # are from the terraform_1.15.9_SHA256SUMS file published with the release.
          terraformVersion = "1.15.9";
          terraformRelease =
            {
              aarch64-darwin = {
                os = "darwin";
                arch = "arm64";
                hash = "sha256-BbJ1hqXX2EEFaQ7MzH7bv0i8PW1Xd0XLYfFjupkK308=";
              };
              x86_64-darwin = {
                os = "darwin";
                arch = "amd64";
                hash = "sha256-PpfEmfrIB0rfo3YDAGYqAVjy/TJRRJZd0AKN7sQIbGs=";
              };
              aarch64-linux = {
                os = "linux";
                arch = "arm64";
                hash = "sha256-CvpsKfYcpeonDpUOQ+UOzyQYtZhQe/WA6K524eZpmxk=";
              };
              x86_64-linux = {
                os = "linux";
                arch = "amd64";
                hash = "sha256-du3Qsi0vJ9PS4JfNeTIJZG9xnPYPAv869iawc2ETfaE=";
              };
            }
            .${system};
          terraformPinned = pkgs.stdenvNoCC.mkDerivation {
            pname = "terraform";
            version = terraformVersion;

            src = pkgs.fetchurl {
              url = "https://releases.hashicorp.com/terraform/${terraformVersion}/terraform_${terraformVersion}_${terraformRelease.os}_${terraformRelease.arch}.zip";
              inherit (terraformRelease) hash;
            };

            nativeBuildInputs = [ pkgs.unzip ];
            dontUnpack = true;

            installPhase = ''
              runHook preInstall
              mkdir -p "$out/bin" "$out/share/licenses/terraform"
              unzip -q "$src" -d release
              install -m755 release/terraform "$out/bin/terraform"
              if [ -f release/LICENSE.txt ]; then
                install -m644 release/LICENSE.txt "$out/share/licenses/terraform/LICENSE.txt"
              fi
              runHook postInstall
            '';

            meta = with pkgs.lib; {
              description = "Terraform infrastructure-as-code CLI";
              homepage = "https://www.terraform.io/";
              license = licenses.bsl11;
              mainProgram = "terraform";
              platforms = [ system ];
            };
          };
          ciShell = pkgs.mkShell {
            packages = with pkgs; [
              actionlint
              git
              gnumake
              shellcheck
              terraformPinned
              yamllint
              (python3.withPackages (
                ps: with ps; [
                  pyyaml
                  jsonschema
                ]
              ))
            ];

            # `--ignore-environment` deliberately removes HOME. Terraform otherwise derives
            # a plugin-cache path below `/`, so give isolated validation a disposable home
            # without overriding the real developer/runner home.
            shellHook = ''
              if [ -z "''${HOME:-}" ]; then
                export HOME="$TMPDIR/nix-home"
                mkdir -p "$HOME"
              fi
            '';
          };

          defaultShell = pkgs.mkShell {
            # Terraform exactly matches .terraform-version and the protected workflows.
            packages = with pkgs; [
              terraformPinned
              tflint
              checkov
              google-cloud-sdk
              gh
              jq
              yq-go
              shellcheck
              yamllint
              actionlint
              pre-commit
              (python3.withPackages (
                ps: with ps; [
                  pyyaml
                  jsonschema
                ]
              ))

            ];

            shellHook = ''
              echo "github-config — the organization as Terraform"
              echo
              echo "  terraform version: $(terraform version -json | ${pkgs.jq}/bin/jq -r .terraform_version)"
              echo
              echo "  terraform init -backend=false && terraform validate && terraform test"
              echo "  actionlint && yamllint --strict .        # what plan.yml runs"
              echo "  python3 scripts/export-ci-variables.py --bootstrap ../bootstrap"
              echo "  python3 scripts/export-idp-groups.py --check"
            '';
          };
        in
        {
          inherit
            ciShell
            defaultShell
            pkgs
            terraformPinned
            ;
        };
    in
    {
      packages = forAllSystems (system: {
        terraform = (perSystem system).terraformPinned;
      });

      devShells = forAllSystems (system: {
        ci = (perSystem system).ciShell;
        default = (perSystem system).defaultShell;
      });

      checks = forAllSystems (system: {
        ci-shell = (perSystem system).ciShell;
        terraform = (perSystem system).terraformPinned;
      });

      formatter = forAllSystems (system: (perSystem system).pkgs.nixfmt);
    };
}

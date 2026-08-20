# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

{
  description = "Toolchain for the mindclade github-config repository";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfreePredicate = package:
            nixpkgs.lib.getName package == "terraform";
        };

        # nixos-25.05's Terraform is too old for this repository's >=1.15 constraint. Keep
        # the broader toolchain on the stable locked channel while installing the same exact
        # HashiCorp release used by CI and .terraform-version. The hashes are from the
        # terraform_1.15.9_SHA256SUMS file published with the release.
        terraformVersion = "1.15.9";
        terraformRelease = {
          aarch64-darwin = {
            os = "darwin";
            arch = "arm64";
            sha256 = "05b27586a5d7d84105690ecccc7edbbf48bc3d6d577745cb61f163ba990adf4f";
          };
          x86_64-darwin = {
            os = "darwin";
            arch = "amd64";
            sha256 = "3e97c499fac8074adfa3760300662a0158f2fd325144965dd0028deec4086c6b";
          };
          aarch64-linux = {
            os = "linux";
            arch = "arm64";
            sha256 = "0afa6c29f61ca5ea270e950e43e50ecf2418b598507bf580e8ae76e1e6699b19";
          };
          x86_64-linux = {
            os = "linux";
            arch = "amd64";
            sha256 = "76edd0b22d2f27d3d2e097cd793209646f719cf60f02ff3af626b07361137da1";
          };
        }.${system};
        terraformPinned = pkgs.stdenvNoCC.mkDerivation {
          pname = "terraform";
          version = terraformVersion;

          src = pkgs.fetchurl {
            url = "https://releases.hashicorp.com/terraform/${terraformVersion}/terraform_${terraformVersion}_${terraformRelease.os}_${terraformRelease.arch}.zip";
            sha256 = terraformRelease.sha256;
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
      in
      {
        # ---------------------------------------------------------------------------------
        # CI shell
        # ---------------------------------------------------------------------------------
        # Small on purpose: the `lint` job in plan.yml needs these three and nothing else, and
        # this shell is what it resolves. `default` below carries the full local toolchain.
        #
        # This repository carried .github/actionlint.yaml and .yamllint.yaml with nothing
        # running either, and no flake to supply the binaries if anything had. Both gaps close
        # together — a config with no runner is a description of a standard, not a gate.
        devShells.ci = pkgs.mkShell {
          packages = with pkgs; [
            actionlint
            shellcheck # actionlint shells out to it for `run:` blocks; absent, those go unchecked
            yamllint
            (python3.withPackages (ps: with ps; [ pyyaml jsonschema ]))
          ];
        };

        devShells.default = pkgs.mkShell {
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
            (python3.withPackages (ps: with ps; [ pyyaml jsonschema ]))

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
      });
}

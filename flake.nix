# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary
#
{
  description = "Toolchain for the mindclade github-config repository";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
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
          # Terraform tracks build/toolchains/versions.yaml in the monorepo (1.15.9), which is
          # also what every workflow here pins. The channel pin makes the shell reproducible;
          # it does not by itself make this terraform equal that one, so the shellHook says
          # what it got.
          packages = with pkgs; [
            terraform
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

            # bash 5. macOS ships 3.2.57 and always will — its licence changed at bash 4 — and
            # scripts/export-idp-groups.sh uses `declare -A`, which bash 3.2 parses as an
            # INDEXED array assignment and dies on with "engineering: unbound variable".
            # That script keeps its own version check for anyone running it outside this
            # shell; this is what makes the shell itself safe.
            bashInteractive
          ];

          shellHook = ''
            echo "github-config — the organization as Terraform"
            echo
            echo "  terraform version: $(terraform version -json | ${pkgs.jq}/bin/jq -r .terraform_version) (workflows pin 1.15.9)"
            echo
            echo "  terraform init -backend=false && terraform validate && terraform test"
            echo "  actionlint && yamllint --strict .        # what plan.yml runs"
            echo "  ./scripts/export-ci-variables.sh --bootstrap ../bootstrap"
            echo "  ./scripts/export-idp-groups.sh --check"
          '';
        };
      });
}

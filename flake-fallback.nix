{
  description = "Bem-te-vi — variante com OpenSpec em prefixo npm local";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        node = pkgs.nodejs_22;
        python = pkgs.python312;

        openspecVersion = "1.7.0";

        libs = pkgs.lib.makeLibraryPath (with pkgs; [
          stdenv.cc.cc.lib
          zlib
          glib
          libGL
          openssl
        ]);
      in
      {
        devShells.default = pkgs.mkShell {
          packages = [
            node
            python
            pkgs.uv
            pkgs.just
            pkgs.sqlite
            pkgs.jq
            pkgs.git
          ];

          env = {
            UV_PYTHON_DOWNLOADS = "never";
            UV_PYTHON = "${python}/bin/python3";
            LD_LIBRARY_PATH = libs;
          };

          shellHook = ''
            # Prefixo npm dentro do projeto: writable, ao contrário do
            # /nix/store onde o npm tentaria instalar por padrão.
            export NPM_CONFIG_PREFIX="$PWD/.npm"
            export PATH="$NPM_CONFIG_PREFIX/bin:$PATH"

            if [ ! -x "$NPM_CONFIG_PREFIX/bin/openspec" ]; then
              echo "instalando openspec@${openspecVersion} em .npm/ ..."
              npm install -g "@fission-ai/openspec@${openspecVersion}"
            fi

            echo "bem-te-vi  ·  node $(node --version)  ·  $(python3 --version)"
            echo "openspec $(openspec --version)"
          '';
        };
      });
}

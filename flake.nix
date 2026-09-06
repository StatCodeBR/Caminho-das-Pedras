{
  description = "Caminho das Pedras — descoberta de dados abertos brasileiros";

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

        # Wheels binárias (onnxruntime, numpy, torch) esperam um FHS.
        # Sem isto: "libstdc++.so.6 not found" ao importar.
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
            # uv baixa CPython pré-compilado que não roda no NixOS.
            UV_PYTHON_DOWNLOADS = "never";
            UV_PYTHON = "${python}/bin/python3";
            LD_LIBRARY_PATH = libs;
            # Cache do modelo ONNX dentro do projeto, espelhando o container.
            FASTEMBED_CACHE_PATH = "./.cache/fastembed";
          };

          shellHook = ''
            # O OpenSpec não embute suas dependências no tarball do npm, então
            # não dá para empacotá-lo com um simples fetchurl. Instalamos num
            # prefixo dentro do projeto, que é gravável — ao contrário do
            # prefixo padrão, que fica no /nix/store somente leitura.
            export NPM_CONFIG_PREFIX="$PWD/.npm"
            export PATH="$NPM_CONFIG_PREFIX/bin:$PATH"

            if [ ! -x "$NPM_CONFIG_PREFIX/bin/openspec" ]; then
              echo "instalando openspec@${openspecVersion} em .npm/ ..."
              npm install -g "@fission-ai/openspec@${openspecVersion}" \
                --silent --no-fund --no-audit
            fi

            echo ""
            echo "  caminho-das-pedras"
            echo "  node $(node --version)  ·  $(python3 --version)"
            echo "  openspec $(openspec --version 2>/dev/null || echo 'FALHOU')"
            echo ""
          '';
        };
      });
}

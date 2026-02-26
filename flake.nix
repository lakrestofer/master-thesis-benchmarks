{
  inputs = {
    nixpkgs.url = "github:cachix/devenv-nixpkgs/rolling";
    systems.url = "github:nix-systems/default";
    devenv.url = "github:cachix/devenv";
    devenv.inputs.nixpkgs.follows = "nixpkgs";
  };

  nixConfig = {
    extra-trusted-public-keys = "devenv.cachix.org-1:w1cLUi8dv3hnoSPGAuibQv+f9TZLr6cv/Hm9XgU50cw=";
    extra-substituters = "https://devenv.cachix.org";
  };

  outputs =
    {
      self,
      nixpkgs,
      devenv,
      systems,
      ...
    }@inputs:
    let
      forEachSystem = nixpkgs.lib.genAttrs (import systems);
    in
    {
      devShells = forEachSystem (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};

          # jdkPackage = pkgs.jdk8;
          jdkPackage = pkgs.jdk11;
        in
        {
          default = devenv.lib.mkShell {
            inherit inputs pkgs;
            modules = [
              {
                languages.java = {
                  enable = true;
                  jdk.package = jdkPackage;
                };
                # # https://devenv.sh/reference/options/
                packages = with pkgs; [
                  # (async-profiler.override { jdk = jdkPackage; })
                  bash-language-server
                ];

                # enterShell = ''
                #   hello
                # '';

                # processes.hello.exec = "hello";
                languages.python = {
                  enable = true;
                  # package = python-pkg;
                  manylinux.enable = true;
                  uv = {
                    enable = true;
                    sync.enable = true;
                    sync.allPackages = true;
                  };
                  venv.enable = true;
                };

              }
            ];
          };
        }
      );
    };
}

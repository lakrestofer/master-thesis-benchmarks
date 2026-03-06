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

          jdkPackage = pkgs.jdk8;
          # jdkPackage = pkgs.jdk11;

          python-pkg = (
            pkgs.python3.withPackages (pp: [
              pp.pyqt6
            ])
          );

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
                packages =
                  (with pkgs; [
                    bash-language-server
                    uv
                    # Qt6 system dependencies for cadquery-visualizer
                    libGL
                    libxkbcommon
                    xorg.libX11
                    xorg.libXrender
                    xorg.libXext
                    xorg.libxcb
                    xorg.xcbutilwm
                    xorg.xcbutilimage
                    xorg.xcbutilkeysyms
                    xorg.xcbutilrenderutil
                    xorg.xcbutilcursor
                    wayland
                    fontconfig
                    freetype
                    zstd
                    glib
                    zlib
                    # pypy3
                  ])
                  ++ [
                    python-pkg
                  ];

                env = {
                  # PYTHON_JIT = 1;
                  # makeLibraryPath adds /lib to derivation outputs.
                  # For raw string paths like /run/opengl-driver/lib, concatenate directly.
                  LD_LIBRARY_PATH =
                    (pkgs.lib.makeLibraryPath (
                      with pkgs;
                      [
                        libGL
                        libxkbcommon
                        xorg.libX11
                        xorg.libXrender
                        xorg.libXext
                        xorg.libxcb
                        xorg.xcbutilwm
                        xorg.xcbutilimage
                        xorg.xcbutilkeysyms
                        xorg.xcbutilrenderutil
                        xorg.xcbutilcursor
                        wayland
                        fontconfig
                        freetype
                        zstd
                        glib
                        zlib
                      ]
                    ))
                    + ":/run/opengl-driver/lib:/run/opengl-driver-32/lib";
                };

                # enterShell = ''
                #   hello
                # '';

                # processes.hello.exec = "hello";
                languages.python = {
                  enable = true;
                  package = python-pkg;
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

# Source import status

The Stepora `stepora/` directory has been initialized, but **the full 122-file PHP source tree has not yet been pushed**. The package `stepora_extracted_git_import_v0_9_1.zip` created in ChatGPT contains the extracted full application, SQL, documentation, and original PNG logo.

To finish the import, extract the package on a networked machine with authorized GitHub Git credentials and run `bash IMPORT_TO_GITHUB.sh` from `stepora-git-import/`. The script clones this repository, copies files only under `stepora/`, commits and pushes without modifying `ocplab-ansible` or `wireguard-manager`.

Do not add production `.env`, secrets, runtime storage or customer uploads to the repository. The consolidated SQL is for **fresh installations**, not live upgrades.

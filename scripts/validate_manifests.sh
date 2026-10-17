#!/usr/bin/env bash
# Render the Kustomize base and overlays, then check them with kubeconform.
# Downloads pinned Linux or macOS binaries into .tools/ on first use.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="${ROOT}/.tools"
KUSTOMIZE_VERSION="${KUSTOMIZE_VERSION:-5.8.3}"
KUBECONFORM_VERSION="${KUBECONFORM_VERSION:-0.8.0}"
KUBERNETES_VERSION="${KUBERNETES_VERSION:-1.37.0}"

mkdir -p "${TOOLS}"

os="$(uname -s | tr '[:upper:]' '[:lower:]')"
case "${os}" in
  linux|darwin) ;;
  *)
    echo "unsupported OS: ${os}" >&2
    exit 1
    ;;
esac

arch="$(uname -m)"
case "${arch}" in
  x86_64) cpu="amd64" ;;
  aarch64|arm64) cpu="arm64" ;;
  *)
    echo "unsupported architecture: ${arch}" >&2
    exit 1
    ;;
esac

install_tool() {
  local name="$1"
  local version="$2"
  local url="$3"
  local entry="$4"
  local stamp="${TOOLS}/${name}.version"
  if [[ -x "${TOOLS}/${name}" && -f "${stamp}" && "$(cat "${stamp}")" == "${version}" ]]; then
    return
  fi
  local tmp
  tmp="$(mktemp -d)"
  curl -fsSL -o "${tmp}/archive.tar.gz" "${url}"
  tar -C "${TOOLS}" -xzf "${tmp}/archive.tar.gz" "${entry}"
  chmod +x "${TOOLS}/${name}"
  printf '%s\n' "${version}" >"${stamp}"
  rm -rf "${tmp}"
}

install_tool \
  kustomize \
  "${KUSTOMIZE_VERSION}" \
  "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv${KUSTOMIZE_VERSION}/kustomize_v${KUSTOMIZE_VERSION}_${os}_${cpu}.tar.gz" \
  kustomize

install_tool \
  kubeconform \
  "${KUBECONFORM_VERSION}" \
  "https://github.com/yannh/kubeconform/releases/download/v${KUBECONFORM_VERSION}/kubeconform-${os}-${cpu}.tar.gz" \
  kubeconform

export PATH="${TOOLS}:${PATH}"

targets=(base dev staging prod)
for target in "${targets[@]}"; do
  if [[ "${target}" == "base" ]]; then
    source_dir="${ROOT}/deploy/base"
  else
    source_dir="${ROOT}/deploy/overlays/${target}"
  fi
  echo "validating ${target}"
  rendered="$(mktemp)"
  kustomize build "${source_dir}" >"${rendered}"
  if [[ ! -s "${rendered}" ]]; then
    echo "kustomize build produced no output for ${target}" >&2
    exit 1
  fi
  # kubeconform ignores paths that do not end in .yaml, so pass the document on stdin.
  kubeconform \
    -strict \
    -summary \
    -kubernetes-version "${KUBERNETES_VERSION}" \
    - <"${rendered}"
  rm -f "${rendered}"
done

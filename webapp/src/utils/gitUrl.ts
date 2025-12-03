/**
 * Convert amplifier git URL to browser-accessible URL
 *
 * Handles formats (both old and new):
 * - New format: git+https://github.com/user/repo@branch#subdirectory=path
 * - Old format: git@github.com:user/repo.git@branch//path
 * - Old format: https://github.com/user/repo.git@branch//path
 * - Same for gitlab.com and other hosts
 *
 * @param source - Git URL in amplifier format
 * @returns Browser URL or null if not a git source/unparseable
 *
 * @example
 * // New format (used by amplifier collections)
 * toWebUrl('git+https://github.com/user/repo@main#subdirectory=src')
 * // => 'https://github.com/user/repo/tree/main/src'
 *
 * // Old format (backward compatibility)
 * toWebUrl('git@github.com:user/repo.git@main//src')
 * // => 'https://github.com/user/repo/tree/main/src'
 *
 * toWebUrl('local') // => null
 */
export function toWebUrl(source: string): string | null {
  if (source === 'local' || !source.includes('git')) {
    return null;
  }

  try {
    let remaining = source;
    let branch: string | null = null;
    let subdirectory = '';

    // Strip git+ prefix if present (used by amplifier collections)
    if (remaining.startsWith('git+')) {
      remaining = remaining.substring(4);
    }

    // Detect if this is SSH format (git@host:) to avoid false matches
    const isSshFormat = remaining.startsWith('git@') && remaining.includes(':');

    // Extract branch and subdirectory based on format
    if (!isSshFormat) {
      // HTTPS format - try new format first: @branch#subdirectory=path
      const newFormatMatch = remaining.match(/@([^#]+)#subdirectory=(.+)$/);
      if (newFormatMatch) {
        branch = newFormatMatch[1];
        subdirectory = newFormatMatch[2];
        remaining = remaining.substring(0, newFormatMatch.index);
        if (!remaining.endsWith('.git')) {
          remaining = remaining + '.git';
        }
      } else {
        // Try old format: .git@branch//path (backward compatibility)
        const oldFormatMatch = remaining.match(/\.git@([^/]+)\/\/(.+)$/);
        if (oldFormatMatch) {
          branch = oldFormatMatch[1];
          subdirectory = oldFormatMatch[2];
          remaining = remaining.substring(0, oldFormatMatch.index) + '.git';
        } else {
          // Try just branch (new format: @branch# or @branch$, avoiding the SSH git@)
          const branchNewMatch = remaining.match(/@([^#]+)(#|$)/);
          if (branchNewMatch && branchNewMatch.index !== undefined) {
            branch = branchNewMatch[1];
            remaining = remaining.substring(0, branchNewMatch.index);
            if (!remaining.endsWith('.git')) {
              remaining = remaining + '.git';
            }
          }

          // Try just subdirectory (new format: #subdirectory=path)
          const subdirNewMatch = remaining.match(/#subdirectory=(.+)$/);
          if (subdirNewMatch && subdirNewMatch.index !== undefined) {
            subdirectory = subdirNewMatch[1];
            remaining = remaining.substring(0, subdirNewMatch.index);
            if (!remaining.endsWith('.git')) {
              remaining = remaining + '.git';
            }
          } else {
            // Try just subdirectory (old format: .git//path or just //path)
            const subdirOldMatch = remaining.match(/\.git\/\/(.+)$/);
            if (subdirOldMatch && subdirOldMatch.index !== undefined) {
              subdirectory = subdirOldMatch[1];
              remaining = remaining.substring(0, subdirOldMatch.index) + '.git';
            }
          }
        }
      }
    } else {
      // SSH format - use .git as anchor to avoid matching git@host:
      // Try old format: .git@branch//path (backward compatibility)
      const oldFormatMatch = remaining.match(/\.git@([^/]+)\/\/(.+)$/);
      if (oldFormatMatch) {
        branch = oldFormatMatch[1];
        subdirectory = oldFormatMatch[2];
        remaining = remaining.substring(0, oldFormatMatch.index) + '.git';
      } else {
        // Try just branch (old format: .git@branch)
        const branchOldMatch = remaining.match(/\.git@([^/#]+)$/);
        if (branchOldMatch && branchOldMatch.index !== undefined) {
          branch = branchOldMatch[1];
          remaining = remaining.substring(0, branchOldMatch.index) + '.git';
        }

        // Try just subdirectory (old format: .git//path)
        const subdirOldMatch = remaining.match(/\.git\/\/(.+)$/);
        if (subdirOldMatch && subdirOldMatch.index !== undefined) {
          subdirectory = subdirOldMatch[1];
          remaining = remaining.substring(0, subdirOldMatch.index) + '.git';
        }
      }
    }

    // Parse SSH format: git@host:user/repo or git@host:user/repo.git
    const sshMatch = remaining.match(/^git@([^:]+):(.+?)(\.git)?$/);
    if (sshMatch) {
      const [, host, path] = sshMatch;
      if (path.includes('@')) {
        // Unparsed branch specification (e.g., branches with slashes)
        return null;
      }
      return formatWebUrl(host, path, branch, subdirectory);
    }

    // Parse HTTPS format: https://host/user/repo or https://host/user/repo.git
    const httpsMatch = remaining.match(/^https:\/\/([^/]+)\/(.+?)(\.git)?$/);
    if (httpsMatch) {
      const [, host, path] = httpsMatch;
      if (path.includes('@')) {
        // Unparsed branch specification (e.g., branches with slashes)
        return null;
      }
      return formatWebUrl(host, path, branch, subdirectory);
    }

    console.warn(`Unable to parse git URL: ${source}`);
    return null;
  } catch (error) {
    console.warn(`Unable to parse git URL: ${source}`, error);
    return null;
  }
}

function formatWebUrl(
  host: string,
  path: string,
  branch: string | null,
  subdirectory: string
): string {
  const subdir = subdirectory ? `/${subdirectory}` : '';

  if (!branch) {
    return `https://${host}/${path}${subdir}`;
  }

  // GitLab uses /-/tree/ instead of /tree/
  if (host.includes('gitlab')) {
    return `https://${host}/${path}/-/tree/${branch}${subdir}`;
  }

  // GitHub and most others use /tree/
  return `https://${host}/${path}/tree/${branch}${subdir}`;
}
